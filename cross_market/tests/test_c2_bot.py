"""
Item 10, Phase 1 (Round 85): the Telegram C2 bot, 100% offline. The transport is a
fake; no socket is ever opened. What must be true: it refuses to start without a
token or an allowlist; it never answers a group chat, an unlisted user or a stale
update; every update is acknowledged before it is acted on; /halt is two-step and
writes ONLY the sentinel; /resume is console-only; the token never appears in
anything it prints; the launcher is guarded like the others.
"""
import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from cross_market.interfaces import c2_bot as c2

NOW = datetime(2026, 9, 6, 2, 0, tzinfo=timezone.utc)
TOKEN = "123456789:AAH-super-secret-token-value"
ADMIN = 42


class FakeTransport:
    """Records sends; hands out queued update batches; can be told to fail."""

    def __init__(self, batches=None, fail_send=False):
        self.batches = list(batches or [])
        self.sent = []
        self.fail_send = fail_send
        self.errors = 0
        self.last_error = None
        self.polls = 0

    def get_updates(self, offset, timeout_s):
        self.polls += 1
        self.last_offset = offset
        return self.batches.pop(0) if self.batches else []

    def send(self, chat_id, text):
        if self.fail_send:
            return False
        self.sent.append((chat_id, text))
        return True


class C2Base(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.pid = self.root / "c2_bot.pid"
        self.offset = self.root / "c2_bot_offset.json"
        self.halt = self.root / "HALT.flag"
        self.settings = c2.Settings(token=TOKEN, admins=frozenset({ADMIN}), stale_seconds=120.0)
        self.log_lines = []

    def tearDown(self):
        self.temp.cleanup()

    def log(self, message):
        self.log_lines.append(message)

    def readers(self, **overrides):
        base = dict(
            processes=lambda: [{"role": "supervisor", "pid": 46740, "rss_mb": 41.2, "started": "x"},
                               {"role": "collector", "pid": 38548, "rss_mb": 88.0, "started": "x"},
                               {"role": "watcher", "pid": 49812, "rss_mb": 35.5, "started": "x"}],
            collector_status=lambda: {"pid": 38548, "dexes_listed": ["abcd", "cash"], "age_s": 61.0},
            watcher_status=lambda: {"running": True, "holder_pid": 49812, "newest_macro_age_s": 120.0, "newest_macro_tags": False},
            exporter_status=lambda: {"running": True, "holder_pid": 56412, "lead_lag_last_run": None, "lead_lag_ready": False,
                                     "lead_lag_reasons": ["span 13.8h < 24h", "points 165 < 200"],
                                     "lead_lag_eta": "2026-09-06T01:39:49+00:00", "lead_lag_points": 165, "lead_lag_span_hours": 13.8},
            bankroll=lambda: {"safe": 1234.56, "escrow": 321.0, "hurdle": 0.1675, "line": "[TAX] ledger OK"},
            paper_state=lambda: {"cash": 5000.0, "funding_collected": 12.5, "realized_pnl": -3.0, "saved_at": "2026-09-05T15:00:00Z",
                                 "positions": {"XPL": {"coin": "XPL", "capital": 2500.0, "entry_funding_apr": 0.42,
                                                       "funding_accrued": 4.2, "hours_held": 30.5}}},
            placed_bets=lambda: [{"placed_at": "2026-09-04T11:00:00Z", "selection": "Chiefs", "decimal_odds": 1.91,
                                  "stake": 50.0, "book": "betmgm", "bet_kind": "single"}],
        )
        base.update(overrides)
        return c2.Readers(**base)

    def ctx(self, readers=None, actor="tester(42)"):
        return c2.Context(readers=readers or self.readers(), halt_path=self.halt, now=NOW, actor=actor)

    @staticmethod
    def update(text, user=ADMIN, chat=ADMIN, chat_type="private", age_s=5, uid=None, username="monarch"):
        return {"update_id": uid if uid is not None else int(time.time() * 1000) % 1_000_000,
                "message": {"message_id": 1, "date": int(NOW.timestamp()) - age_s,
                            "chat": {"id": chat, "type": chat_type}, "from": {"id": user, "username": username},
                            "text": text}}


class TestSettingsAndAuth(C2Base):

    def test_settings_parse_and_refuse_fail_closed(self):
        self.assertEqual(c2.parse_admin_ids("42, 7;x -3\n9"), frozenset({42, 7, -3, 9}))
        self.assertEqual(c2.parse_admin_ids(None), frozenset())
        self.assertIn("TELEGRAM_BOT_TOKEN", c2.Settings.from_env({}, registry=lambda n: None).refusal())
        self.assertIn("C2_ADMIN_IDS", c2.Settings.from_env({"TELEGRAM_BOT_TOKEN": TOKEN}, registry=lambda n: None).refusal())
        self.assertIsNone(c2.Settings.from_env({"TELEGRAM_BOT_TOKEN": TOKEN, "C2_ADMIN_IDS": "42"}, registry=lambda n: None).refusal())
        # the user-level registry is the fallback, and a registry error is "unset", never a crash
        reg = lambda name: {"TELEGRAM_BOT_TOKEN": TOKEN, "C2_ADMIN_IDS": "42,43"}[name]
        s = c2.Settings.from_env({}, registry=reg)
        self.assertEqual((s.token, s.admins), (TOKEN, frozenset({42, 43})))
        self.assertIsNone(c2.user_env("X", {}, registry=lambda n: (_ for _ in ()).throw(OSError("no key"))))
        self.assertEqual(c2.redact("tok=%s here" % TOKEN, TOKEN), "tok=<token> here")
        self.assertEqual(c2.redact(None, TOKEN), "")

    def test_parse_update_and_authorize_matrix(self):
        self.assertIsNone(c2.parse_update({"update_id": 1, "edited_message": {"text": "/status"}}))
        self.assertIsNone(c2.parse_update({"update_id": 2, "message": {"chat": {"id": 1, "type": "private"}, "from": {"id": 42}}}))
        self.assertIsNone(c2.parse_update("junk"))
        self.assertIsNone(c2.parse_update({"message": {"text": "/x", "chat": {"id": 1}}}))            # no update_id
        ok = c2.parse_update(self.update("/status", uid=7))
        self.assertEqual((ok.update_id, ok.chat_id, ok.chat_type, ok.user_id, ok.username, ok.text), (7, 42, "private", 42, "monarch", "/status"))
        now_ts = NOW.timestamp()
        self.assertEqual(c2.authorize(ok, c2.Settings(TOKEN, frozenset()), now_ts), (False, "no allowlist configured"))
        group = c2.parse_update(self.update("/status", chat=-100, chat_type="supergroup"))
        self.assertEqual(c2.authorize(group, self.settings, now_ts)[1], "not a private chat (supergroup)")
        stranger = c2.parse_update(self.update("/status", user=7, chat=7))
        self.assertEqual(c2.authorize(stranger, self.settings, now_ts)[1], "sender 7 not allowlisted")
        stale = c2.parse_update(self.update("/halt CONFIRM", age_s=500))
        self.assertTrue(c2.authorize(stale, self.settings, now_ts)[1].startswith("stale update (age 500s > 120s)"))
        undated = c2.parse_update({"update_id": 9, "message": {"text": "/status", "chat": {"id": 42, "type": "private"}, "from": {"id": 42}}})
        self.assertEqual(c2.authorize(undated, self.settings, now_ts), (False, "no timestamp"))
        self.assertEqual(c2.authorize(ok, self.settings, now_ts), (True, "ok"))


class TestProcessing(C2Base):

    def test_rejections_are_silent_and_every_update_is_acknowledged_first(self):
        transport = FakeTransport()
        updates = [self.update("/halt CONFIRM", chat=-1, chat_type="group", uid=10),
                   self.update("/status", user=7, chat=7, uid=11),
                   self.update("/status", age_s=999, uid=12),
                   {"update_id": 13, "channel_post": {"text": "/status"}},
                   self.update("hello there", uid=14),
                   self.update("/help", uid=15)]
        stats = c2.process_updates(updates, self.settings, self.readers(), transport, self.offset, self.halt, NOW, self.log)
        self.assertEqual((stats["handled"], stats["rejected"], stats["ignored"], stats["sent"], stats["next_update_id"]), (1, 3, 2, 1, 16))
        self.assertEqual(len(transport.sent), 1)
        self.assertEqual(transport.sent[0][0], ADMIN)
        self.assertIn("/status", transport.sent[0][1])
        self.assertEqual(c2.load_offset(self.offset), 16)
        rejected = [line for line in self.log_lines if "rejected update" in line]
        self.assertEqual(len(rejected), 3)
        self.assertIn("not a private chat (group)", rejected[0]) ; self.assertIn("sender 7 not allowlisted", rejected[1])
        self.assertIn("stale update", rejected[2])
        self.assertFalse(self.halt.exists(), "a group-chat /halt CONFIRM must never touch the flag")
        # a failed send is counted, never raised; a dry run logs instead of sending
        failing = FakeTransport(fail_send=True)
        stats = c2.process_updates([self.update("/help", uid=20)], self.settings, self.readers(), failing, self.offset, self.halt, NOW, self.log)
        self.assertEqual((stats["sent"], stats["send_failed"]), (0, 1))
        stats = c2.process_updates([self.update("/help", uid=21)], self.settings, self.readers(), failing, self.offset, self.halt, NOW, self.log, dry_run=True)
        self.assertEqual((stats["sent"], stats["send_failed"]), (1, 0))
        self.assertTrue(any("dry-run reply" in line for line in self.log_lines))

    def test_run_loop_advances_the_offset_and_survives_transport_errors(self):
        class Flaky(FakeTransport):
            def get_updates(self, offset, timeout_s):
                self.polls += 1
                self.last_offset = offset
                if self.polls == 1:
                    return None                              # transport error
                return self.batches.pop(0) if self.batches else []
        c2.save_offset(self.offset, 100)
        transport = Flaky(batches=[[self.update("/help", uid=100)], [self.update("/help", uid=101)]])
        slept = []
        totals = c2.run_loop(self.settings, self.readers(), transport, self.offset, self.halt, interval=5, max_polls=4,
                             log=self.log, sleep=slept.append, clock=lambda: NOW)
        self.assertEqual((totals["polls"], totals["errors"], totals["handled"], totals["sent"]), (4, 1, 2, 2))
        self.assertEqual(transport.last_offset, 102)                                # offset follows the acknowledgements
        self.assertEqual(c2.load_offset(self.offset), 102)
        self.assertEqual(slept[0], 5)                                               # the error waited one interval
        self.assertTrue(any("transport error" in line for line in self.log_lines))


class TestCommands(C2Base):

    def test_status_bankroll_positions_render_and_a_dead_source_does_not_kill_the_reply(self):
        text = c2.dispatch("/status", self.ctx())
        for expect in ("supervisor: pid 46740, 41.2 MB", "collector: pid 38548, 88.0 MB", "exporter:  NOT RUNNING", "c2 bot:    NOT RUNNING",
                       "collector status: pid 38548, 2 dex(es), written 61s ago", "watcher: RUNNING pid 49812; macro stamp 2.0 min old; tags no",
                       "exporter: RUNNING pid 56412", "Item 18: last run never; macro series NOT READY - span 13.8h < 24h; points 165 < 200",
                       "Item 18 ETA: 2026-09-06T01:39:49+00:00", "HALT.flag: absent"):
            self.assertIn(expect, text)
        text = c2.dispatch("/bankroll", self.ctx())
        for expect in ("safe deployable:   $1,234.56", "tax escrow:        $321.00", "hurdle: 16.75%", "[TAX] ledger OK"):
            self.assertIn(expect, text)
        text = c2.dispatch("/positions", self.ctx())
        for expect in ("POSITIONS - PAPER", "cash $5,000.00 · 1 open", "XPL: capital $2,500.00, entry APR 42.0%, accrued $4.20, held 30.5 h",
                       "SPORTS BETS (placed_bets: 1 recorded, newest 1) - PAPER", "Chiefs @ 1.91 stake $50.00 betmgm single"):
            self.assertIn(expect, text)

        def boom():
            raise RuntimeError("db locked")
        text = c2.dispatch("/status", self.ctx(self.readers(watcher_status=boom, collector_status=lambda: None)))
        self.assertIn("watcher unavailable: RuntimeError: db locked", text)
        self.assertIn("collector status file: missing", text)
        self.assertIn("exporter: RUNNING pid 56412", text)                          # the rest still renders
        self.assertIn("Tax Reserve Agent unavailable: RuntimeError", c2.dispatch("/bankroll", self.ctx(self.readers(bankroll=boom))))
        text = c2.dispatch("/positions", self.ctx(self.readers(paper_state=lambda: None, placed_bets=lambda: [])))
        self.assertIn("paper state file: missing", text) ; self.assertIn("none recorded", text)
        self.assertEqual(c2.dispatch("/help", self.ctx()), c2.HELP_TEXT)
        self.assertEqual(c2.dispatch("/status@PentaDeskBot", self.ctx())[:6], "STATUS")
        self.assertIn("Unknown command /nuke", c2.dispatch("/nuke", self.ctx()))
        self.assertIsNone(c2.dispatch("just chatting", self.ctx()))
        self.assertIsNone(c2.dispatch("", self.ctx()))

    def test_halt_is_two_step_writes_only_the_sentinel_and_resume_is_console_only(self):
        first = c2.dispatch("/halt", self.ctx())
        self.assertIn("/halt CONFIRM", first) ; self.assertIn("never killed", first)
        self.assertFalse(self.halt.exists())
        engaged = c2.dispatch("/halt CONFIRM funding spike on XPL", self.ctx(actor="monarch(42)"))
        self.assertTrue(engaged.startswith("HALT ENGAGED at 2026-09-06T02:00:00+00:00 by monarch(42) (funding spike on XPL)"))
        meta = json.loads(self.halt.read_text(encoding="utf-8"))
        self.assertEqual((meta["who"], meta["when"], meta["reason"], meta["source"]),
                         ("monarch(42)", NOW.isoformat(), "funding spike on XPL", "c2_bot"))
        again = c2.dispatch("/halt CONFIRM", self.ctx())
        self.assertIn("already ENGAGED since 2026-09-06T02:00:00+00:00 by monarch(42)", again)
        self.assertIn("PRESENT since 2026-09-06T02:00:00+00:00 by monarch(42) - execution HALTED", c2.dispatch("/status", self.ctx()))
        resume = c2.dispatch("/resume", self.ctx())
        self.assertIn("Console-only", resume) ; self.assertIn("PRESENT", resume) ; self.assertTrue(self.halt.exists())
        self.halt.unlink()
        self.assertIn("/halt CONFIRM", c2.dispatch("/killall", self.ctx()))                 # the alias is two-step too
        self.assertFalse(self.halt.exists())
        self.assertIn("absent", c2.dispatch("/resume", self.ctx()))
        # a flag written by hand (not JSON) is still recognised as a halt
        self.halt.write_text("manual", encoding="utf-8")
        self.assertIn("already ENGAGED since ? by ?", c2.dispatch("/halt CONFIRM", self.ctx()))

    def test_chunking_keeps_lines_whole_and_under_the_limit(self):
        text = "\n".join("line %04d " % i + "x" * 90 for i in range(100))         # ~10,000 chars
        pieces = c2.chunk(text)
        self.assertGreater(len(pieces), 2)
        self.assertTrue(all(len(p) <= c2.MAX_REPLY_CHARS for p in pieces))
        self.assertEqual("\n".join(pieces), text)
        self.assertEqual(c2.chunk(""), [""])
        long_line = "y" * 9000
        self.assertEqual([len(p) for p in c2.chunk(long_line)], [4000, 4000, 1000])


class TestTransportAndCli(C2Base):

    def test_transport_uses_the_injected_http_and_never_raises(self):
        calls = []

        def http(method, params):
            calls.append((method, dict(params)))
            if method == "getUpdates":
                return {"ok": True, "result": [self.update("/help", uid=5), "junk"]}
            return {"ok": True, "result": {"message_id": 9}}
        transport = c2.TelegramTransport(TOKEN, http=http)
        updates = transport.get_updates(7, timeout_s=5)
        self.assertEqual([u["update_id"] for u in updates], [5])
        self.assertEqual(calls[0], ("getUpdates", {"timeout": 5, "allowed_updates": ["message"], "offset": 7}))
        self.assertTrue(transport.send(42, "hi"))
        self.assertEqual(calls[1][1]["chat_id"], 42)
        self.assertIn(TOKEN, transport.url("getUpdates"))
        self.assertNotIn(TOKEN, c2.redact(transport.url("getUpdates"), TOKEN))

        def broken(method, params):
            raise OSError("network down %s" % TOKEN)
        transport = c2.TelegramTransport(TOKEN, http=broken)
        self.assertIsNone(transport.get_updates(None, 1)) ; self.assertFalse(transport.send(42, "x"))
        self.assertEqual(transport.errors, 2)
        self.assertNotIn(TOKEN, transport.last_error) ; self.assertIn("<token>", transport.last_error)
        self.assertIsNone(c2.TelegramTransport(TOKEN, http=lambda m, p: {"ok": False}).get_updates(None, 1))

    def test_status_never_prints_the_token_and_reports_the_flag(self):
        info = c2.bot_status(self.pid, self.offset, self.halt, self.settings, now=NOW)
        self.assertEqual((info["running"], info["token_set"], info["admins"], info["next_update_id"], info["halt_meta"]), (False, True, 1, None, None))
        text = c2.format_bot_status(info)
        self.assertIn("token: set", text) ; self.assertNotIn(TOKEN, text) ; self.assertIn("HALT.flag absent", text)
        self.assertNotIn(TOKEN, json.dumps(info))
        c2.dispatch("/halt CONFIRM drill", self.ctx(actor="monarch(42)"))
        c2.save_offset(self.offset, 77)
        info = c2.bot_status(self.pid, self.offset, self.halt, self.settings, now=NOW, alive=lambda pid: True,
                             probe=lambda pid: "pythonw -m cross_market.interfaces.c2_bot --log-file x")
        self.pid.write_text("%d\n" % (os.getpid() + 40_000), encoding="utf-8")
        info = c2.bot_status(self.pid, self.offset, self.halt, self.settings, now=NOW, alive=lambda pid: True,
                             probe=lambda pid: "pythonw -m cross_market.interfaces.c2_bot --log-file x")
        self.assertTrue(info["running"]) ; self.assertEqual(info["next_update_id"], 77)
        text = c2.format_bot_status(info)
        self.assertIn("c2 bot RUNNING - pid", text) ; self.assertIn("HALT.flag PRESENT", text) ; self.assertIn("by monarch(42)", text)
        # a live process that is not the bot is a stale lock
        info = c2.bot_status(self.pid, self.offset, self.halt, self.settings, now=NOW, alive=lambda pid: True,
                             probe=lambda pid: "python -m unittest")
        self.assertFalse(info["running"]) ; self.assertTrue(info["stale_pid_file"])

    def test_main_refuses_without_token_or_admins_then_polls_once_under_the_lock(self):
        from cross_market.ingestors import pid_lock
        common = ["--pid-file", str(self.pid), "--offset-file", str(self.offset), "--halt-flag", str(self.halt)]
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(c2.main(["--status"] + common, environ={}, registry=lambda n: None), c2.STATUS_EXIT_STOPPED)
        self.assertIn("token: unset", fake_print.call_args_list[0].args[0])
        with mock.patch("builtins.print") as fake_print:
            self.assertEqual(c2.main(["--once"] + common, environ={}, registry=lambda n: None), c2.EXIT_REFUSED)
            self.assertEqual(c2.main(["--once"] + common, environ={"TELEGRAM_BOT_TOKEN": TOKEN}, registry=lambda n: None), c2.EXIT_REFUSED)
        printed = " ".join(str(c.args[0]) for c in fake_print.call_args_list)
        self.assertIn("refusing to start", printed) ; self.assertNotIn(TOKEN, printed)
        self.assertFalse(self.pid.exists(), "a refused start never claims the lock")
        # one dry-run poll: the injected http hands out a fresh /help; the reply lands in the log; the lock is released
        env = {"TELEGRAM_BOT_TOKEN": TOKEN, "C2_ADMIN_IDS": "42"}
        fresh = self.update("/help", uid=500)
        fresh["message"]["date"] = int(time.time())
        calls = []

        def http(method, params):
            calls.append(method)
            return {"ok": True, "result": [fresh]} if method == "getUpdates" else {"ok": True}
        held = {}
        with mock.patch.object(pid_lock, "install_cleanup", lambda *a, **k: held.setdefault("pid", pid_lock.read_pid_file(self.pid))), \
                mock.patch("builtins.print") as fake_print:
            rc = c2.main(["--once", "--dry-run", "--interval", "0"] + common, environ=env, registry=lambda n: None,
                         http=http, readers=self.readers())
        self.assertEqual(rc, 0)
        self.assertEqual(held.get("pid"), os.getpid()) ; self.assertFalse(self.pid.exists())
        self.assertEqual(calls, ["getUpdates"])                                     # dry run: nothing sent
        printed = " ".join(str(c.args[0]) for c in fake_print.call_args_list)
        self.assertIn("dry-run reply", printed) ; self.assertIn("/bankroll", printed) ; self.assertNotIn(TOKEN, printed)
        self.assertEqual(c2.load_offset(self.offset), 501)
        # a live holder makes a newcomer exit 0 without polling
        self.pid.write_text("%d\n" % (os.getpid() + 40_000), encoding="utf-8")
        calls.clear()
        with mock.patch.object(pid_lock, "pid_is_alive", return_value=True), \
                mock.patch.object(pid_lock, "process_cmdline", return_value="pythonw -m cross_market.interfaces.c2_bot"), \
                mock.patch("builtins.print") as fake_print:
            self.assertEqual(c2.main(["--once"] + common, environ=env, registry=lambda n: None, http=http), 0)
        self.assertIn("already_running", " ".join(str(c.args[0]) for c in fake_print.call_args_list))
        self.assertEqual(calls, [])

    def test_the_launcher_is_guarded_and_detached(self):
        dev = Path(__file__).resolve().parents[2]
        bat = (dev / "start_c2_bot.bat").read_text(encoding="utf-8", errors="replace")
        for expect in ("Start-Process", "pythonw", "cross_market.interfaces.c2_bot", "--log-file", "c2_bot.log", "c2_bot --status", "errorlevel 3"):
            self.assertIn(expect, bat)
        self.assertLess(bat.index('set "PYW='), bat.index("if errorlevel 3 ("))
        block = bat[bat.index("if errorlevel 3 ("):bat.index(") else (")]
        for line in block.splitlines():
            if line.strip().startswith("echo"):
                self.assertNotIn(")", line) ; self.assertNotIn("(", line)
        self.assertNotIn("TELEGRAM_BOT_TOKEN=", bat)                                # the token is never in a launcher
