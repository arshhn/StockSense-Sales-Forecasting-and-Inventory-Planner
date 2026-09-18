"""Small exact examples protect the user-facing inventory arithmetic."""

import pytest

from stocksense.inventory import replenishment_plan


def test_uses_only_lead_time_weeks_and_rounds_up():
    plan = replenishment_plan([10.2, 12.5, 1000, 1000], 5, 3, 2, 4)
    assert plan.forecast_during_lead_time == pytest.approx(22.7)
    assert plan.target_stock == pytest.approx(26.7)
    assert plan.replenishment_quantity == 19


def test_available_and_incoming_stock_can_cover_requirement():
    assert replenishment_plan([20, 10], 25, 10, 2, 5).replenishment_quantity == 0
    assert replenishment_plan([0], 0, 0, 1, 0).replenishment_quantity == 0


def test_safety_stock_remains_when_forecast_is_zero():
    assert replenishment_plan([0], 3, 2, 1, 12).replenishment_quantity == 7


@pytest.mark.parametrize("lead_time", [0, -1, 3, 1.5, True])
def test_invalid_lead_time_is_rejected(lead_time):
    with pytest.raises(ValueError):
        replenishment_plan([10, 10], 0, 0, lead_time, 0)


@pytest.mark.parametrize("field", ["current_stock", "on_order", "safety_stock"])
@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), "3", True])
def test_invalid_inventory_inputs_are_rejected(field, value):
    inputs = dict(forecast_sales=[10], current_stock=0, on_order=0,
                  lead_time_weeks=1, safety_stock=0)
    inputs[field] = value
    with pytest.raises(ValueError):
        replenishment_plan(**inputs)


@pytest.mark.parametrize("forecasts", [[], [-1], [float("nan")], [float("inf")]])
def test_invalid_forecasts_are_rejected(forecasts):
    with pytest.raises(ValueError):
        replenishment_plan(forecasts, 0, 0, 1, 0)
