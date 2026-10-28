"""Проверка входных данных: граничные значения и ошибочный ввод без обращения к базе."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.material import MaterialIn
from app.schemas.receipt import ReceiptIn, ReceiptItemIn
from app.schemas.supplier import SupplierIn
from app.schemas.unit import UnitIn


def item(quantity="1", price="10"):
    return ReceiptItemIn(material_id=1, quantity=quantity, price=price)


@pytest.mark.parametrize("quantity", ["0.001", "1", "999999999.999"])
def test_quantity_boundaries_accepted(quantity):
    assert item(quantity=quantity).quantity == Decimal(quantity)


@pytest.mark.parametrize("quantity", ["0", "-0.001", "-5", "0.0001", "1000000000", "abc", ""])
def test_quantity_rejected(quantity):
    with pytest.raises(ValidationError):
        item(quantity=quantity)


@pytest.mark.parametrize("price", ["0", "0.01", "9999999999.99"])
def test_price_boundaries_accepted(price):
    # бесплатная поставка (цена 0) разрешена
    assert item(price=price).price == Decimal(price)


@pytest.mark.parametrize("price", ["-0.01", "0.001", "10000000000", "abc"])
def test_price_rejected(price):
    with pytest.raises(ValidationError):
        item(price=price)


@pytest.mark.parametrize("material_id", [0, -1])
def test_material_id_must_be_positive(material_id):
    with pytest.raises(ValidationError):
        ReceiptItemIn(material_id=material_id, quantity="1", price="1")


def test_receipt_defaults():
    receipt = ReceiptIn(supplier_id=1)
    assert receipt.items == []
    assert receipt.receipt_date is not None


@pytest.mark.parametrize("inn", ["7701234567", "770123456789"])
def test_inn_accepted(inn):
    assert SupplierIn(name="ООО Ромашка", inn=inn).inn == inn


@pytest.mark.parametrize("inn", ["770123456", "77012345678", "7701234567890", "77012345ab", ""])
def test_inn_rejected(inn):
    with pytest.raises(ValidationError, match="ИНН"):
        SupplierIn(name="ООО Ромашка", inn=inn)


@pytest.mark.parametrize("email", ["info@stroybaza.ru", "", None])
def test_email_accepted(email):
    supplier = SupplierIn(name="ООО Ромашка", inn="7701234567", email=email)
    assert supplier.email == (email or None)


@pytest.mark.parametrize("email", ["info", "@stroybaza.ru", "info@"])
def test_email_rejected(email):
    with pytest.raises(ValidationError):
        SupplierIn(name="ООО Ромашка", inn="7701234567", email=email)


def test_supplier_strips_spaces_and_empty_fields_become_none():
    supplier = SupplierIn(name="  ООО Ромашка  ", inn="7701234567", phone="", address="")
    assert supplier.name == "ООО Ромашка"
    assert supplier.phone is None
    assert supplier.address is None


def test_material_has_no_stock_field():
    # остаток нельзя задать при создании или изменении материала (ПР-1)
    material = MaterialIn(name="Цемент", unit_id=1, stock=100)
    assert not hasattr(material, "stock")


@pytest.mark.parametrize("name", ["", "   ", "x" * 201])
def test_material_name_rejected(name):
    with pytest.raises(ValidationError):
        MaterialIn(name=name, unit_id=1)


@pytest.mark.parametrize(("name", "short_name"), [("", "кг"), ("Килограмм", ""), ("x" * 51, "кг")])
def test_unit_rejected(name, short_name):
    with pytest.raises(ValidationError):
        UnitIn(name=name, short_name=short_name)
