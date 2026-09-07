<#
.SYNOPSIS
  One-off proof that Windows Task Scheduler -> fomc_drill_2026-09-16.bat -> latency_sniper --record-loop works on
  THIS machine, into scratch. Round 118 (Ruling R116-1.F). The operator runs it by hand; it is the one link no
  in-process rehearsal can exercise.

.DESCRIPTION
  Registers a temporary task, Monarch_Rehearsal_Probe, with the SAME shape as the drill task - the current user,
  interactive logon, default settings (which include DisallowStartIfOnBatteries and StopIfGoingOnBatteries, exactly
  as Monarch_FOMC_Drill has them) - firing in -LeadMinutes minutes and running the TRACKED batch with two arguments:
  -Seconds and a scratch books directory under cross_market\data\rehearsals\probe_<stamp>\books. It waits for the
  run, reports the task's LastTaskResult and the number of stamps written (expect ~3 per second), then unregisters
  the probe task. Monarch_FOMC_Drill is never touched. If the laptop is on battery at fire time the probe does not
  start - and that is precisely the finding the battery-flag decision is about.

  Writes: the scratch books directory; one line pair appended to cross_market\data\fomc_drill_2026-09-16.log
  (the batch logs every start and exit there, probe or drill).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File cross_market\scripts\probe_scheduled_task.ps1 -WhatIf
      shows what would be registered; registers nothing.
  powershell -ExecutionPolicy Bypass -File cross_market\scripts\probe_scheduled_task.ps1
      registers, waits (~LeadMinutes + Seconds + 30 s), reports, unregisters. Exit 0 on PROBE OK, 1 on PROBE FAILED.
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [int]$Seconds = 20,
    [int]$LeadMinutes = 2,
    [switch]$KeepTask
)
$ErrorActionPreference = 'Stop'
$name = 'Monarch_Rehearsal_Probe'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)                       # ...\DEV
$bat = Join-Path $root 'cross_market\scripts\fomc_drill_2026-09-16.bat'
if (-not (Test-Path $bat)) { throw "tracked batch missing: $bat" }
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$books = Join-Path $root "cross_market\data\rehearsals\probe_$stamp\books"
$at = (Get-Date).AddMinutes($LeadMinutes)
$expected = $Seconds * 3                                                            # three registered tokens, one stamp each per second

$action = New-ScheduledTaskAction -Execute "`"$bat`"" -Argument ("{0} `"{1}`"" -f $Seconds, $books)
$trigger = New-ScheduledTaskTrigger -Once -At $at
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive
$settings = New-ScheduledTaskSettingsSet                                            # defaults = the drill task's battery behaviour

Write-Host ("probe: {0} fires {1} local, runs {2} {3} `"{4}`" (expect ~{5} stamps)" -f $name, $at.ToString('HH:mm:ss'), $bat, $Seconds, $books, $expected)
if (-not $PSCmdlet.ShouldProcess($name, "register a one-off task firing at $($at.ToString('HH:mm:ss'))")) { exit 0 }

if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) { Unregister-ScheduledTask -TaskName $name -Confirm:$false }
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Principal $principal -Settings $settings | Out-Null
Write-Host "registered $name"

$deadline = $at.AddSeconds($Seconds + 90)
do {
    Start-Sleep -Seconds 5
    $task = Get-ScheduledTask -TaskName $name
    $info = Get-ScheduledTaskInfo -TaskName $name
} while ((Get-Date) -lt $deadline -and ($task.State -eq 'Running' -or $info.LastRunTime -lt $at))

$stamps = @(Get-ChildItem -Path $books -Filter 'clob_*.json' -ErrorAction SilentlyContinue).Count
Write-Host ("state {0}; last run {1}; last result {2} (0 = ok, 267011 = never ran); stamps {3} of ~{4}" -f $task.State, $info.LastRunTime, $info.LastTaskResult, $stamps, $expected)
if (-not $KeepTask) { Unregister-ScheduledTask -TaskName $name -Confirm:$false; Write-Host "unregistered $name" }

if ($info.LastTaskResult -ne 0 -or $stamps -lt [math]::Floor(0.8 * $expected)) {
    Write-Host 'PROBE FAILED: Task Scheduler -> batch -> recorder did not produce the expected stamps (on battery? not logged in? see the log line in cross_market\data\fomc_drill_2026-09-16.log)'
    exit 1
}
Write-Host 'PROBE OK: Task Scheduler launched the tracked batch and the recorder wrote stamps into scratch'
exit 0
