"""
Unit tests for HL_Monarch Round 20: BasisHarvester Execution Adapter Integration
Tests running BasisHarvester in pure paper mode vs routing through OrderExecutor.
"""
from unittest.mock import MagicMock
import pytest

from execution.basis_harvester import BasisHarvester


def test_basis_harvester_paper_mode_default():
    harvester = BasisHarvester(starting_cash=10000.0)
    assert harvester.executor is None

    opp = {
        "coin": "SOL",
        "spread_bps": 5.0,
        "funding_apr": 25.0,
        "net_apr": 24.5,
        "holding_days": 10.0,
        "mark_px": 150.0,
        "perp_sz_decimals": 2,
        "spot_sz_decimals": 2,
    }
    pos = harvester.open_position(opp, notional_per_leg=300.0)
    assert pos is not None
    assert pos["coin"] == "SOL"
    assert "SOL" in harvester.positions
    assert harvester.cash < 10000.0

    closed = harvester.close_position("SOL")
    assert closed is not None
    assert "SOL" not in harvester.positions


def test_basis_harvester_with_mock_executor_success():
    mock_executor = MagicMock()
    mock_executor.execute_basis_pair.return_value = {
        "spot": MagicMock(filled_sz=2.0),
        "perp": MagicMock(filled_sz=2.0),
        "residual_sz": 0.0,
        "hedged": True,
        "aborted": None,
    }
    mock_executor.close_basis_pair.return_value = {
        "residual_sz": 0.0,
        "unwound": True,
    }

    harvester = BasisHarvester(starting_cash=10000.0, executor=mock_executor)
    opp = {
        "coin": "SOL",
        "spread_bps": 5.0,
        "funding_apr": 25.0,
        "net_apr": 24.5,
        "holding_days": 10.0,
        "mark_px": 150.0,
        "perp_sz_decimals": 2,
        "spot_sz_decimals": 2,
    }
    pos = harvester.open_position(opp, notional_per_leg=300.0)
    assert pos is not None
    assert mock_executor.execute_basis_pair.called
    call_kwargs = mock_executor.execute_basis_pair.call_args[1]
    assert call_kwargs["coin"] == "SOL"

    closed = harvester.close_position("SOL")
    assert closed is not None
    assert mock_executor.close_basis_pair.called


def test_basis_harvester_with_mock_executor_aborted():
    mock_executor = MagicMock()
    # Simulate an aborted pair execution (e.g. risk clamp mismatch)
    mock_executor.execute_basis_pair.return_value = {
        "spot": MagicMock(filled_sz=1.0),
        "perp": None,
        "residual_sz": 1.0,
        "hedged": False,
        "aborted": "spot leg was re-sized; perp leg NOT placed",
    }

    harvester = BasisHarvester(starting_cash=10000.0, executor=mock_executor)
    opp = {
        "coin": "SOL",
        "spread_bps": 5.0,
        "funding_apr": 25.0,
        "net_apr": 24.5,
        "holding_days": 10.0,
        "mark_px": 150.0,
        "perp_sz_decimals": 2,
        "spot_sz_decimals": 2,
    }
    initial_cash = harvester.cash
    pos = harvester.open_position(opp, notional_per_leg=300.0)
    # Must fail safely and not record open position or drain cash
    assert pos is None
    assert "SOL" not in harvester.positions
    assert harvester.cash == initial_cash
