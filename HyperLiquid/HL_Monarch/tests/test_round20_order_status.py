"""
Unit tests for HL_Monarch Round 20: Order Status and Open Orders Reconciliation API
"""
import json
from unittest.mock import patch
import pytest

from api.rest_client import HyperliquidRestClient


class FakeResponse:
    def __init__(self, data: dict):
        self.data = data

    def read(self):
        return json.dumps(self.data).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def test_get_open_orders():
    client = HyperliquidRestClient()
    fake_orders = [
        {"coin": "BTC", "oid": 1001, "side": "B", "sz": "0.1", "limitPx": "60000.0"},
        {"coin": "ETH", "oid": 1002, "side": "A", "sz": "1.5", "limitPx": "3000.0"}
    ]
    user_addr = "0x1234567890abcdef1234567890abcdef12345678"

    with patch("urllib.request.urlopen", return_value=FakeResponse(fake_orders)) as mock_urlopen:
        res = client.get_open_orders(user_addr)
        assert res == fake_orders
        req = mock_urlopen.call_args[0][0]
        sent_body = json.loads(req.data.decode("utf-8"))
        assert sent_body == {"type": "openOrders", "user": user_addr}


def test_get_order_status():
    client = HyperliquidRestClient()
    fake_status = {
        "status": "order",
        "order": {
            "order": {"coin": "BTC", "side": "B", "limitPx": "60000.0", "sz": "0.1", "oid": 1001},
            "status": "filled"
        }
    }
    user_addr = "0x1234567890abcdef1234567890abcdef12345678"

    with patch("urllib.request.urlopen", return_value=FakeResponse(fake_status)) as mock_urlopen:
        res = client.get_order_status(user_addr, oid=1001)
        assert res == fake_status
        req = mock_urlopen.call_args[0][0]
        sent_body = json.loads(req.data.decode("utf-8"))
        assert sent_body == {"type": "orderStatus", "user": user_addr, "oid": 1001}
