"""
Monarch strategy plug-ins.

Every strategy subclasses `BaseStrategy` (see `base.py`), which is what gets it a
capital bucket, an after-tax edge hurdle, and tax-aware position sizing without
each strategy reimplementing them - or, more to the point, without any strategy
being free to skip them.
"""
from .base import BaseStrategy, Opportunity

__all__ = ["BaseStrategy", "Opportunity"]
