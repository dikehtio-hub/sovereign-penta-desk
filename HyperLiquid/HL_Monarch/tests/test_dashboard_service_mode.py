"""
Round 36 Ruling 3.A: one ingester. The dashboard is a read-only viewer while a
service collector is alive, and a standalone ingester only when none is.

The decision and the badge are pure functions so they can be pinned without a
terminal: which mode a start-up lands in, and what the header says when the
world changes underneath a running dashboard.
"""
import io
import sys
from pathlib import Path

from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors.market_collector import read_service_pid
from ui.components import (STALLED_AFTER_SECONDS, append_dashboard_event, build_header_panel,
                           ingestion_badge, newest_snapshot_age_seconds, novel_dex_badge,
                           read_collector_status)


def test_read_service_pid_is_none_when_absent_or_junk(tmp_path):
    assert read_service_pid(tmp_path / "nope.pid") is None
    junk = tmp_path / "junk.pid"
    junk.write_text("abc", encoding="utf-8")
    assert read_service_pid(junk) is None
    good = tmp_path / "collector.pid"
    good.write_text(" 4242\n", encoding="utf-8")
    assert read_service_pid(good) == 4242


def test_start_up_lands_in_read_only_when_a_service_is_alive():
    mode, badge = ingestion_badge(alive=True, pid=4242, started_read_only=None)
    assert mode == "read_only"
    assert badge == "[dim]Service: RUNNING (PID 4242) · Read-Only Mode[/dim]"


def test_start_up_falls_back_to_standalone_when_no_service():
    mode, badge = ingestion_badge(alive=False, pid=None, started_read_only=None)
    assert mode == "standalone"
    assert badge == "[bold yellow]Service: STOPPED · Standalone Ingestion Active[/bold yellow]"


def test_a_read_only_dashboard_whose_service_died_says_so_loudly():
    """Its tables are going stale and nothing is ingesting - the one state that must not look calm."""
    mode, badge = ingestion_badge(alive=False, pid=4242, started_read_only=True)
    assert mode == "orphaned"
    assert "STOPPED" in badge and "No ingestion" in badge and "start_collector.bat" in badge
    assert badge.startswith("[bold red]")


def test_a_standalone_dashboard_joined_by_a_service_asks_for_a_restart():
    """Its embedded collector yields maintenance but still polls: two REST budgets until restarted."""
    mode, badge = ingestion_badge(alive=True, pid=99, started_read_only=False)
    assert mode == "dual"
    assert "PID 99" in badge and "restart" in badge.lower()


def test_a_live_service_that_writes_nothing_is_stalled_not_calm():
    """Round 37 (cross-check 3.1): the state a process probe cannot see."""
    mode, badge = ingestion_badge(alive=True, pid=4242, started_read_only=True, newest_snapshot_age_s=120.4)
    assert mode == "stalled"
    assert badge == "[bold red]Service: STALLED (PID 4242) · No snapshots written in 120s; restart service[/bold red]"
    # Fresh data, or no data yet to age, is not a stall.
    assert ingestion_badge(True, 4242, True, newest_snapshot_age_s=30.0)[0] == "read_only"
    assert ingestion_badge(True, 4242, True, newest_snapshot_age_s=None)[0] == "read_only"
    assert ingestion_badge(True, 4242, True, newest_snapshot_age_s=STALLED_AFTER_SECONDS)[0] == "read_only"
    # A stall outranks the dual warning: stale tables matter more than a restart nag.
    assert ingestion_badge(True, 4242, False, newest_snapshot_age_s=100.0)[0] == "stalled"
    # A dead service is orphaned/standalone regardless of age - stall is an ALIVE-service state.
    assert ingestion_badge(False, 4242, True, newest_snapshot_age_s=999.0)[0] == "orphaned"
    assert ingestion_badge(False, None, None, newest_snapshot_age_s=999.0)[0] == "standalone"


def test_the_stall_threshold_scales_with_the_poll_interval_above_a_floor():
    """Round 38 (cross-check 3.1): four missed cycles, never under 45s, derived in settings."""
    from config.settings import REST_POLL_INTERVAL, STALLED_FLOOR_SECONDS, stalled_after_seconds
    from config import settings

    assert STALLED_AFTER_SECONDS is settings.STALLED_AFTER_SECONDS      # the UI re-exports, it does not redefine
    assert STALLED_AFTER_SECONDS == stalled_after_seconds(REST_POLL_INTERVAL)
    assert stalled_after_seconds(8.0) == STALLED_FLOOR_SECONDS == 45.0   # (8 + 2) x 4 = 40 sits under the floor
    assert stalled_after_seconds(20.0) == 88.0                          # a slower poll raises the bar, no false alarms
    assert stalled_after_seconds(1.0) == 45.0                           # a faster poll never drops below it
    # And the badge honours whatever the derived value is.
    assert ingestion_badge(True, 1, True, newest_snapshot_age_s=STALLED_AFTER_SECONDS + 0.1)[0] == "stalled"


def test_newest_snapshot_age_reads_millisecond_timestamps_and_tolerates_junk():
    now = 1_788_000_100.0
    rows = [{"timestamp": 1_788_000_000_000}, {"timestamp": 1_788_000_040_000}, {"timestamp": None},
            {"coin": "no-ts"}, "junk"]
    assert newest_snapshot_age_seconds(rows, now=now) == 60.0
    assert newest_snapshot_age_seconds([], now=now) is None
    assert newest_snapshot_age_seconds([{"timestamp": 0}], now=now) is None
    assert newest_snapshot_age_seconds([{"timestamp": 1_788_000_200_000}], now=now) == 0.0   # never negative


def test_the_header_panel_carries_the_badge():
    panel = build_header_panel(1_000_000.0, 2_000_000.0, {"main": 1_000_000.0}, active_tab="ALL",
                               status="[dim]Service: RUNNING (PID 4242) · Read-Only Mode[/dim]")
    buffer = io.StringIO()
    Console(file=buffer, width=200, force_terminal=False, color_system=None).print(panel)
    text = buffer.getvalue()
    assert "Service: RUNNING (PID 4242)" in text and "Read-Only Mode" in text
    # And the header still renders without one.
    build_header_panel(1_000_000.0, 2_000_000.0, {"main": 1_000_000.0}, active_tab="ALL")


def test_a_novel_dex_shows_as_an_amber_badge_from_the_collector_status_file(tmp_path, monkeypatch):
    """
    Round 48 (Ruling 48-2). The hourly cycle warns in a console window that may
    be closed or minimised; the dashboard reads the collector's status file and
    shows the same fact where the operator is looking.
    """
    import json
    from collectors.market_collector import write_collector_status
    from ui.terminal_dashboard import TerminalDashboard
    import config.settings as settings

    assert novel_dex_badge([]) == "" and novel_dex_badge(None) == ""
    assert novel_dex_badge(["newdex", "Other", "newdex", ""]) == \
        "[bold dark_orange]⚠ NOVEL DEX: newdex, other · refused until classified[/bold dark_orange]"

    import time
    path = tmp_path / "collector_status.json"
    assert read_collector_status(path) == {}                                       # absent: nothing claimed
    assert write_collector_status(path, {"unclassified_dexs": ["newdex"], "checked_at": 1_788_000_000.0})
    assert json.loads(path.read_text(encoding="utf-8"))["unclassified_dexs"] == ["newdex"]
    assert read_collector_status(path, max_age_s=None)["unclassified_dexs"] == ["newdex"]
    assert read_collector_status(path, max_age_s=3600.0, now=1_788_000_100.0)["unclassified_dexs"] == ["newdex"]
    assert read_collector_status(path, max_age_s=60.0, now=1_788_000_100.0) == {}   # stale: nothing claimed
    # Round 49 (Ruling 49-1): two hours by default - a dead collector's last write is history.
    assert read_collector_status(path, now=1_788_000_000.0 + 7199.0)["unclassified_dexs"] == ["newdex"]
    assert read_collector_status(path, now=1_788_000_000.0 + 7201.0) == {}
    assert read_collector_status(path) == {}                                       # that stamp is weeks old now
    path.write_text("{not json", encoding="utf-8")
    assert read_collector_status(path) == {}

    # The header composes the service badge and the drift badge - from a FRESH file only.
    monkeypatch.setattr(settings, "COLLECTOR_STATUS_PATH", path)
    dash = TerminalDashboard.__new__(TerminalDashboard)
    assert dash._header_status("[dim]Service: RUNNING (PID 1) · Read-Only Mode[/dim]") == \
        "[dim]Service: RUNNING (PID 1) · Read-Only Mode[/dim]"
    write_collector_status(path, {"unclassified_dexs": ["newdex"], "checked_at": time.time()})
    assert dash._header_status("[dim]svc[/dim]") == "[dim]svc[/dim]  " + novel_dex_badge(["newdex"])
    write_collector_status(path, {"unclassified_dexs": ["newdex"], "checked_at": time.time() - 3 * 3600})
    assert dash._header_status("[dim]svc[/dim]") == "[dim]svc[/dim]"                # stale: no badge
    write_collector_status(path, {"unclassified_dexs": [], "checked_at": time.time()})
    assert dash._header_status("") == ""


def test_the_collector_checks_perp_dexs_at_start_up_and_writes_the_status_file(tmp_path, monkeypatch):
    """Round 49 (Ruling 49-2): the badge is live from minute 0, not minute 60."""
    import json
    import collectors.market_collector as mc

    class Client:
        def __init__(self, payload):
            self.payload = payload

        def get_perp_dexs(self):
            if isinstance(self.payload, Exception):
                raise self.payload
            return self.payload

    path = tmp_path / "collector_status.json"
    monkeypatch.setattr(mc, "COLLECTOR_STATUS_PATH", path)
    collector = mc.MarketCollector.__new__(mc.MarketCollector)
    collector.maintenance, collector.yield_to_service, collector._yield_logged = True, False, False
    collector.rest_client = Client([None, {"name": "xyz"}, {"name": "para"}, {"name": "NewDex"}, {}])
    assert collector._check_perp_dexs() == ["newdex"]
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["unclassified_dexs"] == ["newdex"]
    assert written["dexes_listed"] == ["newdex", "para", "xyz"]
    assert written["checked_at"] > 1_700_000_000 and written["pid"] > 0
    # A failed lookup writes nothing and raises nothing - the previous file stands.
    collector.rest_client = Client(RuntimeError("429"))
    assert collector._check_perp_dexs() == []
    assert json.loads(path.read_text(encoding="utf-8"))["unclassified_dexs"] == ["newdex"]
    # And the dashboard shows what was just written.
    import config.settings as settings
    from ui.terminal_dashboard import TerminalDashboard
    monkeypatch.setattr(settings, "COLLECTOR_STATUS_PATH", path)
    assert "NOVEL DEX: newdex" in TerminalDashboard.__new__(TerminalDashboard)._header_status("")
    # Round 50 closeout (R49-Q2): an embedded collector that a service has joined still checks
    # and warns, but leaves the file to the service - the file is not touched.
    embedded = mc.MarketCollector.__new__(mc.MarketCollector)
    embedded.maintenance, embedded.yield_to_service, embedded._yield_logged = True, True, False
    embedded.rest_client = Client([None, {"name": "xyz"}, {"name": "otherdex"}])
    monkeypatch.setattr(mc, "service_collector_alive", lambda *a, **k: True)
    before = path.read_text(encoding="utf-8")
    assert embedded._check_perp_dexs() == ["otherdex"]
    assert path.read_text(encoding="utf-8") == before
    monkeypatch.setattr(mc, "service_collector_alive", lambda *a, **k: False)     # the service died: it owns again
    assert embedded._check_perp_dexs() == ["otherdex"]
    assert json.loads(path.read_text(encoding="utf-8"))["unclassified_dexs"] == ["otherdex"]


def test_the_dashboard_logs_its_start_stop_and_crash(tmp_path, monkeypatch):
    """
    Round 49 (Ruling 49-1). The viewer died twice today with nothing to read
    afterwards. A frame that fails to render is logged (first three, then
    counted); an exception that escapes the loop is logged with its traceback
    and re-raised; a clean exit logs stop with the count.
    """
    import json
    import config.settings as settings
    import ui.terminal_dashboard as td

    log = tmp_path / "dashboard.jsonl"
    assert append_dashboard_event(log, "dashboard_start", mode="read_only", service_pid=42)
    assert append_dashboard_event(log, "dashboard_crash", error="RuntimeError: boom", traceback="tb")
    lines = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()]
    assert [l["event"] for l in lines] == ["dashboard_start", "dashboard_crash"]
    assert lines[0]["mode"] == "read_only" and lines[0]["service_pid"] == 42 and lines[0]["pid"] > 0
    assert lines[1]["traceback"] == "tb" and lines[1]["ts"].endswith("+00:00")
    assert append_dashboard_event(tmp_path, "nope") is False                        # a directory: unwritable, no raise

    monkeypatch.setattr(settings, "DASHBOARD_LOG_PATH", log)
    monkeypatch.setattr(td, "console", type("C", (), {"print": staticmethod(lambda *a, **k: None)})())
    monkeypatch.setattr(td.time, "sleep", lambda *_: None)

    class FakeLive:
        def __init__(self, *args, **kwargs):
            self.updates = 0

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def update(self, layout):
            self.updates += 1
            if self.updates == 1:
                raise ValueError("bad frame")                                   # logged, loop continues
            dash.running = False                                                # then a clean exit

    dash = td.TerminalDashboard.__new__(td.TerminalDashboard)
    dash.running = True
    dash.generate_layout = lambda: "layout"
    monkeypatch.setattr(td, "Live", FakeLive)
    dash._run_live_loop(fullscreen=False, refresh_rate=0.0)
    events = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()][2:]
    assert [e["event"] for e in events] == ["dashboard_frame_error", "dashboard_stop"]
    assert "ValueError: bad frame" in events[0]["error"] and "Traceback" in events[0]["traceback"]
    assert events[1]["frame_errors"] == 1

    class CrashingLive(FakeLive):
        def __enter__(self):
            raise RuntimeError("terminal gone")

    dash.running = True
    monkeypatch.setattr(td, "Live", CrashingLive)
    try:
        dash._run_live_loop(fullscreen=False, refresh_rate=0.0)
    except RuntimeError as e:
        assert "terminal gone" in str(e)                                        # re-raised, not swallowed
    else:
        raise AssertionError("the crash must propagate")
    last = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert last["event"] == "dashboard_crash" and "terminal gone" in last["error"] and "Traceback" in last["traceback"]
    assert dash.running is False


def test_a_read_only_dashboard_relaunches_a_dead_service_once_per_cooldown_and_alerts(tmp_path, monkeypatch):
    """
    Round 53 (Rulings 53-1/53-2). Three silent service deaths in one day; the
    viewer that noticed each one did nothing. Now a dashboard that STARTED read-
    only logs the death, alerts once per episode, issues the detached relaunch
    at most once per cooldown, and logs when the service is back. A standalone
    dashboard is the ingester itself and never relaunches.
    """
    from ui.terminal_dashboard import TerminalDashboard

    class Alerter:
        def __init__(self):
            self.down, self.stale = [], []

        def alert_service_down(self, pid, reason="process gone"):
            self.down.append(pid)

        def alert_status_stale(self, age, max_age):
            self.stale.append(round(age))

    events, relaunches = [], []
    log = lambda event, **f: events.append((event, f))
    dash = TerminalDashboard.__new__(TerminalDashboard)
    dash.service_mode, dash.service_pid, dash._service_alive = True, 4242, True
    dash._watchdog_last_relaunch, dash._service_dead_since, dash._status_stale_alerted = 0.0, None, False
    alerter = Alerter()
    kw = dict(relaunch=lambda: relaunches.append(1) or True, alerter=alerter, log=log, enabled=True, cooldown=300.0)

    assert dash.service_watchdog(True, now=1000.0, **kw) is None                 # alive: nothing to do
    assert dash.service_watchdog(False, now=1005.0, **kw) == "relaunched"        # dies: log, alert, relaunch
    assert [e for e, _ in events] == ["service_dead", "service_relaunch"]
    assert alerter.down == [4242] and relaunches == [1]
    assert dash.service_watchdog(False, now=1010.0, **kw) == "dead"              # still dead: no second relaunch
    assert dash.service_watchdog(False, now=1305.0, **kw) == "relaunched"        # cooldown passed: try again
    assert len(relaunches) == 2 and alerter.down == [4242]                       # one alert per episode
    assert dash.service_watchdog(True, now=1400.0, **kw) == "back"
    assert events[-1][0] == "service_back" and events[-1][1]["dead_for_s"] == 395.0
    assert dash._service_dead_since is None
    # A relaunch whose command cannot be issued is logged as such.
    assert dash.service_watchdog(False, now=2000.0, relaunch=lambda: False, alerter=alerter, log=log,
                                 enabled=True, cooldown=300.0) == "relaunch_failed"
    assert events[-1] == ("service_relaunch", {"issued": False, "service_pid": 4242})
    # Watchdog disabled: the death is still logged and alerted, nothing is launched.
    dash._service_dead_since, dash._watchdog_last_relaunch = None, 0.0
    assert dash.service_watchdog(False, now=3000.0, relaunch=lambda: relaunches.append(9), alerter=alerter,
                                 log=log, enabled=False, cooldown=300.0) == "dead"
    assert 9 not in relaunches
    # A STANDALONE dashboard never relaunches: it is the ingester.
    dash.service_mode = False
    assert dash.service_watchdog(False, now=4000.0, **kw) is None
    # relaunch_service refuses when the launcher does not exist, and never raises.
    assert TerminalDashboard.relaunch_service(tmp_path / "missing.bat") is False

    # Stale status file while the service is alive: one alert per episode, reset when fresh.
    import json
    import time
    dash.service_mode, dash._service_alive = True, True
    status = tmp_path / "collector_status.json"
    status.write_text(json.dumps({"unclassified_dexs": [], "checked_at": time.time() - 3 * 3600}), encoding="utf-8")
    assert dash.status_stale_watch(status, alerter=alerter, log=log) is True
    assert dash.status_stale_watch(status, alerter=alerter, log=log) is True
    assert alerter.stale == [10800] and events[-1][0] == "status_stale"
    status.write_text(json.dumps({"unclassified_dexs": [], "checked_at": time.time()}), encoding="utf-8")
    assert dash.status_stale_watch(status, alerter=alerter, log=log) is False
    assert dash._status_stale_alerted is False
    dash._service_alive = False
    status.write_text(json.dumps({"unclassified_dexs": [], "checked_at": 1.0}), encoding="utf-8")
    assert dash.status_stale_watch(status, alerter=alerter, log=log) is False    # dead service: the watchdog's job
