"""
Unit tests for HL_Monarch Round 20: Exchange Transport Layer
Tests post_action, URL routing (testnet vs mainnet), rate limiting, and retry backoff.
"""
import json
import urllib.error
from unittest.mock import MagicMock, patch
import pytest

from api.rest_client import HyperliquidRestClient
from config.settings import EXCHANGE_API_URL, TESTNET_EXCHANGE_API_URL


class FakeResponse:
    def __init__(self, data: dict):
        self.data = data

    def read(self):
        return json.dumps(self.data).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def test_post_action_testnet_routing():
    client = HyperliquidRestClient()
    fake_payload = {
        "action": {"type": "order", "orders": []},
        "nonce": 12345678,
        "signature": {"r": "0x1", "s": "0x2", "v": 27},
        "vaultAddress": None,
    }
    expected_response = {"status": "ok", "response": {"type": "order"}}

    with patch("urllib.request.urlopen", return_value=FakeResponse(expected_response)) as mock_urlopen:
        result = client.post_action(fake_payload, testnet=True)
        assert result == expected_response
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == TESTNET_EXCHANGE_API_URL
        assert json.loads(req.data.decode("utf-8")) == fake_payload


def test_post_action_mainnet_routing():
    client = HyperliquidRestClient()
    fake_payload = {
        "action": {"type": "order", "orders": []},
        "nonce": 12345678,
        "signature": {"r": "0x1", "s": "0x2", "v": 27},
        "vaultAddress": None,
    }
    expected_response = {"status": "ok", "response": {"type": "order"}}

    with patch("urllib.request.urlopen", return_value=FakeResponse(expected_response)) as mock_urlopen:
        result = client.post_action(fake_payload, testnet=False)
        assert result == expected_response
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == EXCHANGE_API_URL


def test_post_action_retry_on_429():
    client = HyperliquidRestClient()
    fake_payload = {"action": {"type": "order"}}
    expected_response = {"status": "ok"}

    # Fail twice with 429, then succeed
    http_error_429 = urllib.error.HTTPError("http://test", 429, "Too Many Requests", {}, None)
    with patch("urllib.request.urlopen", side_effect=[http_error_429, http_error_429, FakeResponse(expected_response)]):
        with patch("time.sleep") as mock_sleep:
            res = client.post_action(fake_payload, testnet=True)
            assert res == expected_response
            assert mock_sleep.call_count == 2
