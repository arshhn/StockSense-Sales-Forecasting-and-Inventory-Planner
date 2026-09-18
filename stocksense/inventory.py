"""A transparent inventory simulation, not a stockout or cost optimizer."""

from dataclasses import dataclass
from math import ceil, fsum, isfinite
from numbers import Integral, Real
from typing import Sequence


@dataclass(frozen=True)
class InventoryPlan:
    lead_time_weeks: int
    forecast_during_lead_time: float
    safety_stock: float
    current_stock: float
    on_order: float
    target_stock: float
    replenishment_quantity: int


def _nonnegative_finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite, nonnegative number.")
    numeric = float(value)
    if not isfinite(numeric) or numeric < 0:
        raise ValueError(f"{name} must be a finite, nonnegative number.")
    return numeric


def replenishment_plan(
    forecast_sales: Sequence[float],
    current_stock: float,
    on_order: float,
    lead_time_weeks: int,
    safety_stock: float,
) -> InventoryPlan:
    """Round up max(0, lead-time forecast + safety - current - incoming).

    Forecast values are consecutive future weeks, in chronological order.
    Lead time is in whole weeks. All incoming stock is assumed to arrive before
    it is needed within that lead time. New replenishment arrives only at the
    end of the lead time; this formula does not model the timing of stockouts.
    Safety stock is entered by the user, not statistically estimated here.
    """
    if isinstance(lead_time_weeks, bool) or not isinstance(lead_time_weeks, Integral):
        raise ValueError("lead_time_weeks must be a positive whole number.")
    if lead_time_weeks < 1 or lead_time_weeks > len(forecast_sales):
        raise ValueError("lead_time_weeks must be within the available forecast horizon.")
    forecasts = [_nonnegative_finite(value, "forecast_sales") for value in forecast_sales]
    current = _nonnegative_finite(current_stock, "current_stock")
    incoming = _nonnegative_finite(on_order, "on_order")
    safety = _nonnegative_finite(safety_stock, "safety_stock")
    try:
        expected = fsum(forecasts[:lead_time_weeks])
    except OverflowError as error:
        raise ValueError("Forecast quantities are too large to calculate reliably.") from error
    target = expected + safety
    if not isfinite(target) or not isfinite(current + incoming):
        raise ValueError("Inventory quantities are too large to calculate reliably.")
    return InventoryPlan(
        lead_time_weeks=int(lead_time_weeks),
        forecast_during_lead_time=expected,
        safety_stock=safety,
        current_stock=current,
        on_order=incoming,
        target_stock=target,
        replenishment_quantity=ceil(max(0.0, target - current - incoming)),
    )
