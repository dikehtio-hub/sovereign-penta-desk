"""
Round 24 audit: a submitted order is not a repeatable request.

`_post` retried every 5xx and every transport exception. For an info read that is
correct. For `/exchange` it is not: those failures arrive with the request's fate
UNKNOWN - the order may already be resting - and the nonce is fixed inside the
signed payload, so the retry is a duplicate of the same order.

Both outcomes are bad and one is quiet:
  * the retry is accepted    -> two positions from one intent;
  * the retry is refused for a duplicate nonce -> a REJECTION handed back for an
    order that IS resting, which invites the caller to place it a third time.

So a write retries only on 429, which is refused on the rate limiter before the
matching engine ever sees it.
"""
import sys
import urllib.error
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.rest_client import HyperliquidRestClient


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        import json
        return json.dumps(self._payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _http(code):
    return urllib.error.HTTPError("http://test", code, "boom", {}, None)


ACTION = {"action": {"type": "order"}, "nonce": 1, "signature": {}}


# ------------------------------------------------- writes: 429 still retries

def test_a_429_is_still_retried_on_a_submission():
    """It was refused on the rate limiter; the engine never saw it."""
    client = HyperliquidRestClient()
    with patch("urllib.request.urlopen",
               side_effect=[_http(429), FakeResponse({"status": "ok"})]):
        with patch("time.sleep"):
            assert client.post_action(ACTION, testnet=True) == {"status": "ok"}


def test_a_retry_after_header_is_honoured():
    client = HyperliquidRestClient()
    err = urllib.error.HTTPError("http://test", 429, "slow down",
                                 {"Retry-After": "7"}, None)
    with patch("urllib.request.urlopen",
               side_effect=[err, FakeResponse({"status": "ok"})]):
        with patch("time.sleep") as slept:
            client.post_action(ACTION, testnet=True)
    assert slept.call_args[0][0] >= 7.0


# ----------------------------------------- writes: everything else does NOT

def test_a_5xx_on_a_submission_is_not_retried():
    calls = []

    def _once(*args, **kwargs):
        calls.append(1)
        raise _http(503)

    client = HyperliquidRestClient()
    with patch("urllib.request.urlopen", side_effect=_once):
        with patch("time.sleep"):
            with pytest.raises(RuntimeError) as exc:
                client.post_action(ACTION, testnet=True)
    assert len(calls) == 1
    assert "ORDER STATE UNKNOWN" in str(exc.value)


def test_a_timeout_on_a_submission_is_not_retried():
    """The most dangerous case: the exchange may have accepted it."""
    calls = []

    def _once(*args, **kwargs):
        calls.append(1)
        raise TimeoutError("read timed out")

    client = HyperliquidRestClient()
    with patch("urllib.request.urlopen", side_effect=_once):
        with patch("time.sleep"):
            with pytest.raises(RuntimeError) as exc:
                client.post_action(ACTION, testnet=True)
    assert len(calls) == 1
    assert "ORDER STATE UNKNOWN" in str(exc.value)


def test_the_submission_error_tells_the_operator_to_reconcile():
    """A retry duplicates the order, so the message has to say so."""
    client = HyperliquidRestClient()
    with patch("urllib.request.urlopen", side_effect=ConnectionResetError("reset")):
        with patch("time.sleep"):
            with pytest.raises(RuntimeError) as exc:
                client.post_action(ACTION, testnet=True)
    message = str(exc.value)
    assert "reconcile" in message.lower()
    assert "duplicate" in message.lower()


def test_a_4xx_on_a_submission_still_raises_plainly():
    client = HyperliquidRestClient()
    with patch("urllib.request.urlopen", side_effect=_http(422)):
        with pytest.raises(urllib.error.HTTPError):
            client.post_action(ACTION, testnet=True)


# ------------------------------------------------- reads keep retrying

def test_a_5xx_on_a_read_is_still_retried():
    """Info endpoints are idempotent; repeating them costs nothing."""
    client = HyperliquidRestClient()
    with patch("urllib.request.urlopen",
               side_effect=[_http(503), _http(503), FakeResponse({"ok": True})]):
        with patch("time.sleep") as slept:
            assert client._post({"type": "meta"}) == {"ok": True}
            assert slept.call_count == 2


def test_a_transport_error_on_a_read_is_still_retried():
    client = HyperliquidRestClient()
    with patch("urllib.request.urlopen",
               side_effect=[TimeoutError("t"), FakeResponse({"ok": True})]):
        with patch("time.sleep"):
            assert client._post({"type": "meta"}) == {"ok": True}


def test_a_read_that_never_recovers_raises_after_its_retries():
    client = HyperliquidRestClient()
    with patch("urllib.request.urlopen", side_effect=_http(503)):
        with patch("time.sleep"):
            with pytest.raises(RuntimeError):
                client._post({"type": "meta"})


def test_post_action_is_the_only_caller_that_disables_retries():
    """Guards the wiring: the flag has to actually reach `_post`."""
    seen = {}

    def _capture(payload, url=None, max_retries=3, idempotent=True):
        seen["idempotent"] = idempotent
        return {"status": "ok"}

    client = HyperliquidRestClient()
    client._post = _capture
    client.post_action(ACTION, testnet=True)
    assert seen["idempotent"] is False
