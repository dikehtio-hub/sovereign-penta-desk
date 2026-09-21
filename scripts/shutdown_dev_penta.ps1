<#
.SYNOPSIS
    Clean shutdown of the Monarch penta-desk pipeline, in one command. Replaces
    the bare $pat regex that HOMEWORK.md's shutdown routine asks the operator
    to paste by hand.

.DESCRIPTION
    WHY THIS EXISTS. HOMEWORK.md's step 3 is a single command-line regex with
    no anchor to this tree. It matches on module names alone, it would take a
    pytest run whose path mentions a daemon module, and it gives the operator
    no way to see what WOULD die before it dies.

    WHY PATH ANCHORING ALONE CANNOT WORK HERE. The 2026-09-21 brief asked for
    matching anchored on "DEV\...". Eight of the ten daemons defeat that: they
    run from C:\Users\ixis1\anaconda\pythonw.exe -- outside this tree -- with
    RELATIVE script paths ("run_collector_service.py --quiet",
    "-u main.py collector"). Neither ExecutablePath nor CommandLine contains
    "DEV\". A path-anchored matcher would miss the collector, the one process
    holding a multi-GB SQLite write-ahead log.

    WHY NOT SIGNALS. shutdown_all.bat documents it: the daemons are detached
    pythonw with no console, so CTRL_BREAK has no console group to reach,
    taskkill without /F posts WM_CLOSE to a window that does not exist, and
    os.kill maps onto TerminateProcess. The cooperative path on this host is
    each daemon's own --stop flag (a sentinel the supervise loop polls).

    WHAT THIS USES INSTEAD. Identity comes from the PID FILES the daemons
    already write under this tree -- what their own --status flags read. A pid
    claimed by a lockfile at a known DEV path is anchored by construction.

      TIER 1  pid-file identity + the documented --stop flag (collector,
              polymarket watcher, cross-market exporter). The collector
              checkpoints its WAL and reports "graceful": true.
      TIER 2  the collector's worker: children of the supervisor pid by
              ParentProcessId, plus any "main.py collector" whose parent is
              DEAD (an orphaned worker carries no anchor of its own).
      TIER 3  the five telemetry exporters. No --stop flag exists, so they
              are matched by signature AND must carry an independent anchor
              to this tree (a DEV-only package, or an executable under DEV).
      TIER 4  stragglers: anything the legacy HOMEWORK pattern would have
              taken that no tier above claimed (a daemon whose pid file was
              deleted, a hand-started collector). Keeps this tool a strict
              superset of the routine it replaces. Loudly labelled.

    WHAT IT WILL NOT TOUCH, EVER.
      - tradingview_mcp.server processes with a LIVE parent. They belong to
        the desktop app / IDE, not this pipeline. Only orphaned ones are
        offered, and only under -IncludeOrphanedMcp.
      - Antigravity's extension host (anything under .antigravity-ide).
      - pytest runs, and any --status / --stop helper invocation.
      - This script's own ancestry, so a shutdown launched from inside an
        agent session cannot kill the session that launched it.

    DRY RUN IS THE DEFAULT. Nothing is stopped unless -Execute is passed. The
    dry run is not cosmetic: it probes every tier-1 daemon with --status
    through the SAME invocation path --stop will use (same interpreter, same
    working directory, same module resolution), so a dry run that passes has
    exercised the code that matters.

.PARAMETER Execute
    Actually stop the daemons. Without it the script only reports.

.PARAMETER IncludeOrphanedMcp
    Also terminate tradingview_mcp.server processes whose parent is gone.
    Live ones are never touched regardless of this switch.

.PARAMETER GracefulTimeoutSec
    Seconds to wait for a tier-1 daemon to exit after its --stop before
    falling back to termination. Default 30.

.EXAMPLE
    pwsh -File scripts\shutdown_dev_penta.ps1
    Dry run. Prints exactly what would be stopped, and why.

.EXAMPLE
    pwsh -File scripts\shutdown_dev_penta.ps1 -Execute
    Graceful stop of tier 1, then tiers 2-4, then a verification sweep.
    Exit code 0 = nothing left running, 1 = something survived.
#>
[CmdletBinding()]
param(
    [switch] $Execute,
    [switch] $IncludeOrphanedMcp,
    [int]    $GracefulTimeoutSec = 30
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$DevRoot  = Split-Path -Parent $PSScriptRoot
$Python   = 'C:\Users\ixis1\anaconda\python.exe'
$GapStart = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')

# The pattern HOMEWORK.md's routine used. Kept verbatim: tier 4 and the final
# verification are defined as "whatever this would have matched".
$LegacyPattern = 'run_collector_service|main\.py collector|polymarket_fetcher|cross_market\.interfaces\.obsidian_exporter|main\.py obsidian|obsidian_sync\.py|Tax_Reserve_Agent\.obsidian_sync|Sports_Desk\.interfaces\.obsidian_exporter|telemetry/obsidian_exporter\.py'

# Never a target, whatever else matches.
$NeverPattern = 'pytest|--status|--stop|\.antigravity-ide|tradingview_mcp'

# Our own ancestry -- walk up so the shell, agent or test runner that
# launched this script is protected.
$Protected = [System.Collections.Generic.HashSet[int]]::new()
$cur = $PID
for ($i = 0; $i -lt 12 -and $cur -gt 0; $i++) {
    [void]$Protected.Add($cur)
    $p = Get-CimInstance Win32_Process -Filter "ProcessId=$cur" -ErrorAction SilentlyContinue
    if (-not $p) { break }
    $cur = [int]$p.ParentProcessId
}

function Write-Head($text) {
    Write-Host ''
    Write-Host ('=' * 78) -ForegroundColor DarkGray
    Write-Host "  $text" -ForegroundColor Cyan
    Write-Host ('=' * 78) -ForegroundColor DarkGray
}

function Get-ProcById([int] $ProcessId) {
    Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
}

function Get-PythonProcs {
    @(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction SilentlyContinue)
}

# Run one of a daemon's own verbs (--status / --stop). ALWAYS from $DevRoot:
# "python -m cross_market..." only resolves with this tree as the working
# directory, and the operator may launch this script from anywhere.
function Invoke-DaemonVerb($Daemon, [string] $Verb) {
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'      # a daemon's stderr is output, not a terminating error
    Push-Location -LiteralPath $DevRoot
    try {
        $out = & $Python @($Daemon.Args) $Verb 2>&1 | ForEach-Object { "$_" }
        [pscustomobject]@{ ExitCode = $LASTEXITCODE; Lines = @($out) }
    }
    catch {
        [pscustomobject]@{ ExitCode = -1; Lines = @("invocation failed: $($_.Exception.Message)") }
    }
    finally {
        Pop-Location
        $ErrorActionPreference = $old
    }
}

function Test-Excluded($proc) {
    if ($Protected.Contains([int]$proc.ProcessId)) { return $true }
    if ($proc.CommandLine -and $proc.CommandLine -match $NeverPattern) { return $true }
    return $false
}

# A tier-3 candidate must be tied to THIS tree by something other than the
# signature that found it.
function Test-AnchoredToDev($proc) {
    $root = [regex]::Escape($DevRoot)
    if ($proc.ExecutablePath -and $proc.ExecutablePath -match $root) { return $true }
    $cl = $proc.CommandLine
    if (-not $cl) { return $false }
    if ($cl -match $root) { return $true }
    # Packages that exist nowhere else on this host.
    if ($cl -match '-m\s+(Sports_Desk|Tax_Reserve_Agent|cross_market)\.') { return $true }
    return $false
}

# ---------------------------------------------------------------- TIER 1 ---
$Tier1 = @(
    @{ Desk = 'hl-collector'
       Pid  = 'HyperLiquid\HL_Monarch\data\collector_service.pid'
       Args = @((Join-Path $DevRoot 'HyperLiquid\HL_Monarch\run_collector_service.py')) }
    @{ Desk = 'polymarket-watcher'
       Pid  = 'Sports_Desk\data\polymarket_drops\polymarket_watcher.pid'
       Args = @('-m', 'cross_market.ingestors.polymarket_fetcher') }
    @{ Desk = 'cross-market-exporter'
       Pid  = 'cross_market\data\cross_market_exporter.pid'
       Args = @('-m', 'cross_market.interfaces.obsidian_exporter') }
)

# ---------------------------------------------------------------- TIER 3 ---
$Tier3 = @(
    @{ Desk = 'telem-hyperliquid'; Sig = 'main\.py\s+obsidian\s+--watch' }
    @{ Desk = 'telem-polymarket';  Sig = 'obsidian_sync\.py\s+--watch' }
    @{ Desk = 'telem-sports';      Sig = 'Sports_Desk\.interfaces\.obsidian_exporter' }
    @{ Desk = 'telem-tax';         Sig = 'Tax_Reserve_Agent\.obsidian_sync' }
    @{ Desk = 'telem-quantlab';    Sig = 'telemetry[\\/]obsidian_exporter\.py' }
)

Write-Head "MONARCH PENTA-DESK SHUTDOWN   gap starts: $GapStart"
if (-not $Execute) {
    Write-Host '  DRY RUN -- nothing will be stopped. Re-run with -Execute to act.' -ForegroundColor Yellow
}
Write-Host "  tree: $DevRoot"

$claimed = [System.Collections.Generic.HashSet[int]]::new()

# --------------------------------------------------------------- SURVEY ---
Write-Head 'TIER 1 - pid-file identity, graceful --stop'
$tier1Live = @()
foreach ($d in $Tier1) {
    $pidPath = Join-Path $DevRoot $d.Pid
    if (-not (Test-Path -LiteralPath $pidPath)) {
        Write-Host ("  {0,-24} no pid file (tier 4 will catch it if it is somehow alive)" -f $d.Desk) -ForegroundColor DarkGray
        continue
    }
    $raw = Get-Content -LiteralPath $pidPath -Raw -ErrorAction SilentlyContinue
    $pidClaim = 0
    if ($raw -and $raw -match '(\d{2,7})') { $pidClaim = [int]$Matches[1] }
    $proc = if ($pidClaim) { Get-ProcById $pidClaim } else { $null }
    if (-not $proc) {
        Write-Host ("  {0,-24} STALE pid {1} -- lock file with no process" -f $d.Desk, $pidClaim) -ForegroundColor Yellow
        continue
    }
    if ($Protected.Contains([int]$proc.ProcessId)) {
        Write-Host ("  {0,-24} pid {1} is in THIS script's own ancestry -- refusing" -f $d.Desk, $pidClaim) -ForegroundColor Red
        continue
    }
    Write-Host ("  {0,-24} pid {1,-7} LIVE" -f $d.Desk, $pidClaim) -ForegroundColor Green
    # Prove the verb path now, read-only: same interpreter, cwd and module
    # resolution that --stop will use.
    $probe = Invoke-DaemonVerb $d '--status'
    $first = @($probe.Lines | Where-Object { $_.Trim() } | Select-Object -First 2 | ForEach-Object {
        $s = $_.Trim(); if ($s.Length -gt 104) { $s.Substring(0, 104) + '...' } else { $s } })
    $ok = ($probe.ExitCode -eq 0)
    Write-Host ("      --status path {0} (exit {1}) {2}" -f $(if ($ok) { 'OK' } else { 'FAILED' }), $probe.ExitCode, ($first -join ' | ')) -ForegroundColor $(if ($ok) { 'DarkGray' } else { 'Red' })
    if (-not $ok) {
        Write-Host '      --stop would NOT resolve from here; this daemon would be force-stopped instead.' -ForegroundColor Red
    }
    [void]$claimed.Add($pidClaim)
    $tier1Live += [pscustomobject]@{ Desk = $d.Desk; ProcessId = $pidClaim; Daemon = $d; VerbOk = $ok }
}

$allPy = Get-PythonProcs      # one snapshot, taken after the probes have exited

Write-Head 'TIER 2 - collector worker (supervisor children + orphans)'
$tier2Live = @()
$sup = $tier1Live | Where-Object Desk -eq 'hl-collector' | Select-Object -First 1
foreach ($w in ($allPy | Where-Object { $_.CommandLine -and $_.CommandLine -match 'main\.py\s+collector' })) {
    if (Test-Excluded $w) { continue }
    $parentId = [int]$w.ParentProcessId
    if ($sup -and $parentId -eq $sup.ProcessId) {
        Write-Host ("  {0,-24} pid {1,-7} child of supervisor {2}" -f 'hl-collector-worker', $w.ProcessId, $sup.ProcessId) -ForegroundColor Green
    }
    elseif (-not (Get-ProcById $parentId)) {
        Write-Host ("  {0,-24} pid {1,-7} ORPHAN - parent {2} is gone (signature-only match)" -f 'hl-collector-worker', $w.ProcessId, $parentId) -ForegroundColor Yellow
    }
    else { continue }          # a live, foreign parent: leave it for tier 4 to label
    [void]$claimed.Add([int]$w.ProcessId)
    $tier2Live += [pscustomobject]@{ Desk = 'hl-collector-worker'; ProcessId = [int]$w.ProcessId }
}
if (-not $tier2Live) { Write-Host '  none' -ForegroundColor DarkGray }

Write-Head 'TIER 3 - telemetry exporters (signature + independent DEV anchor)'
$tier3Live = @()
foreach ($d in $Tier3) {
    $hits = @($allPy | Where-Object { $_.CommandLine -and $_.CommandLine -match $d.Sig -and -not (Test-Excluded $_) })
    if (-not $hits) {
        Write-Host ("  {0,-24} not running" -f $d.Desk) -ForegroundColor DarkGray
        continue
    }
    foreach ($h in $hits) {
        if ($claimed.Contains([int]$h.ProcessId)) { continue }
        if (-not (Test-AnchoredToDev $h)) {
            Write-Host ("  {0,-24} pid {1,-7} MATCHED BUT UNANCHORED -- left for tier 4" -f $d.Desk, $h.ProcessId) -ForegroundColor Yellow
            continue
        }
        Write-Host ("  {0,-24} pid {1,-7} LIVE, anchored" -f $d.Desk, $h.ProcessId) -ForegroundColor Green
        [void]$claimed.Add([int]$h.ProcessId)
        $tier3Live += [pscustomobject]@{ Desk = $d.Desk; ProcessId = [int]$h.ProcessId }
    }
}

Write-Head 'TIER 4 - stragglers the legacy pattern would have taken'
$tier4Live = @()
foreach ($s in ($allPy | Where-Object { $_.CommandLine -and $_.CommandLine -match $LegacyPattern })) {
    if ($claimed.Contains([int]$s.ProcessId) -or (Test-Excluded $s)) { continue }
    $cl = $s.CommandLine; if ($cl.Length -gt 96) { $cl = $cl.Substring(0, 96) + '...' }
    Write-Host ("  {0,-24} pid {1,-7} UNCLAIMED: {2}" -f 'straggler', $s.ProcessId, $cl) -ForegroundColor Yellow
    [void]$claimed.Add([int]$s.ProcessId)
    $tier4Live += [pscustomobject]@{ Desk = 'straggler'; ProcessId = [int]$s.ProcessId }
}
if (-not $tier4Live) { Write-Host '  none - tiers 1-3 account for everything the legacy pattern matches' -ForegroundColor DarkGray }

Write-Head 'TRADINGVIEW MCP - live servers are never touched'
$mcp = @($allPy | Where-Object { $_.CommandLine -and $_.CommandLine -match 'tradingview_mcp\.server' })
$orphans = @()
foreach ($m in $mcp) {
    $parent = Get-ProcById ([int]$m.ParentProcessId)
    if ($parent) {
        Write-Host ("  pid {0,-7} LIVE parent {1} ({2}) -- leaving alone" -f $m.ProcessId, $m.ParentProcessId, $parent.Name) -ForegroundColor DarkGray
    }
    else {
        Write-Host ("  pid {0,-7} ORPHAN (parent {1} gone)" -f $m.ProcessId, $m.ParentProcessId) -ForegroundColor Yellow
        $orphans += [pscustomobject]@{ Desk = 'tradingview-mcp-orphan'; ProcessId = [int]$m.ProcessId }
    }
}
if (-not $mcp) { Write-Host '  none running' -ForegroundColor DarkGray }

# ----------------------------------------------------------------- PLAN ---
$forceSet = @($tier2Live) + @($tier3Live) + @($tier4Live)
if ($IncludeOrphanedMcp) { $forceSet += $orphans }
$targets = @($tier1Live) + $forceSet

Write-Head ("PLAN: {0} process(es) would be stopped" -f $targets.Count)
$targets | ForEach-Object { Write-Host ("  {0,-24} pid {1}" -f $_.Desk, $_.ProcessId) }
if ($orphans.Count -and -not $IncludeOrphanedMcp) {
    Write-Host ("  ({0} orphaned MCP server(s) left running; pass -IncludeOrphanedMcp to include)" -f $orphans.Count) -ForegroundColor Yellow
}

if (-not $Execute) {
    Write-Head 'DRY RUN COMPLETE - nothing was stopped'
    Write-Host "  gap would start: $GapStart"
    exit 0
}

# -------------------------------------------------------------- EXECUTE ---
Write-Head 'STOPPING - tier 1, gracefully'
foreach ($t in $tier1Live) {
    Write-Host ("  {0} --stop ..." -f $t.Desk)
    $r = Invoke-DaemonVerb $t.Daemon '--stop'
    $r.Lines | Where-Object { $_.Trim() } | Select-Object -First 12 | ForEach-Object { Write-Host "      $_" }
    if ($r.ExitCode -ne 0) { Write-Host ("      --stop exit {0}" -f $r.ExitCode) -ForegroundColor Yellow }
}

$deadline = (Get-Date).AddSeconds($GracefulTimeoutSec)
while ((Get-Date) -lt $deadline) {
    if (-not @($tier1Live | Where-Object { Get-ProcById $_.ProcessId })) { break }
    Start-Sleep -Milliseconds 500
}
foreach ($t in $tier1Live) {
    if (Get-ProcById $t.ProcessId) {
        Write-Host ("  {0} did not exit within {1}s -- terminating" -f $t.Desk, $GracefulTimeoutSec) -ForegroundColor Yellow
        Stop-Process -Id $t.ProcessId -Force -ErrorAction SilentlyContinue
    }
    else {
        Write-Host ("  {0} exited cleanly" -f $t.Desk) -ForegroundColor Green
    }
}

Write-Head 'STOPPING - tiers 2, 3 and 4'
foreach ($t in $forceSet) {
    if (Get-ProcById $t.ProcessId) {
        Stop-Process -Id $t.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host ("  {0,-24} pid {1} stopped" -f $t.Desk, $t.ProcessId) -ForegroundColor Green
    }
    else {
        Write-Host ("  {0,-24} pid {1} already gone" -f $t.Desk, $t.ProcessId) -ForegroundColor DarkGray
    }
}

# --------------------------------------------------------------- VERIFY ---
# HOMEWORK step 4, kept as the definition of done: nothing the legacy pattern
# matches may still be running.
Write-Head 'VERIFY'
Start-Sleep -Milliseconds 750
$left = @(Get-PythonProcs | Where-Object { $_.CommandLine -and $_.CommandLine -match $LegacyPattern -and -not (Test-Excluded $_) })
if ($left) {
    Write-Host ("  {0} process(es) STILL RUNNING:" -f $left.Count) -ForegroundColor Red
    $left | ForEach-Object { Write-Host ("    pid {0}  {1}" -f $_.ProcessId, $_.CommandLine) -ForegroundColor Red }
    Write-Host "  gap starts: $GapStart"
    exit 1
}
Write-Host '  0 remaining - safe to shut Windows down normally.' -ForegroundColor Green
Write-Host ''
Write-Host "  GAP STARTS: $GapStart" -ForegroundColor Cyan
Write-Host '  Register it on the next resume: python -m knowledge.ingest.data_gaps  (after editing data_gaps.json)'
exit 0
