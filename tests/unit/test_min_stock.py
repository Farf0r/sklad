"""Правило ПР-8: материал нужно заказать, когда его остаток меньше минимального."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.material import Material
from app.schemas.material import MaterialIn


@pytest.mark.parametrize(
    ("stock", "min_stock", "needs_order", "shortage"),
    [
        ("0", "0", False, "0"),  # минимальный остаток не задан
        ("5", "0", False, "0"),
        ("0", "2.5", True, "2.5"),
        ("9.999", "10", True, "0.001"),  # чуть меньше минимума
        ("10", "10", False, "0"),  # ровно минимум — заказывать ещё рано
        ("10.001", "10", False, "0"),
    ],
)
def test_needs_order(stock, min_stock, needs_order, shortage):
    material = Material(stock=Decimal(stock), min_stock=Decimal(min_stock))
    assert material.needs_order is needs_order
    assert material.shortage == Decimal(shortage)


def test_min_stock_is_zero_by_default():
    assert MaterialIn(name="Цемент", unit_id=1).min_stock == 0


@pytest.mark.parametrize("min_stock", ["0", "0.001", "999999999.999"])
def test_min_stock_accepted(min_stock):
    material = MaterialIn(name="Цемент", unit_id=1, min_stock=min_stock)
    assert material.min_stock == Decimal(min_stock)


@pytest.mark.parametrize("min_stock", ["-0.001", "-1", "1.0001", "1000000000", "abc"])
def test_min_stock_rejected(min_stock):
    with pytest.raises(ValidationError):
        MaterialIn(name="Цемент", unit_id=1, min_stock=min_stock)
