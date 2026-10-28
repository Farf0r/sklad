"""Вспомогательная логика без базы данных: суммы, ввод чисел, сообщения об ошибках, пароли."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.errors import error_message, field_errors
from app.forms import decimal_input
from app.models.receipt import Receipt, ReceiptItem
from app.schemas.receipt import ReceiptItemIn
from app.security import hash_password, verify_password
from app.templating import format_money, format_number


def test_item_amount_rounded_to_kopecks():
    assert ReceiptItem(quantity=Decimal("2.5"), price=Decimal("0.33")).amount == Decimal("0.83")
    assert ReceiptItem(quantity=Decimal("1.005"), price=Decimal("1")).amount == Decimal("1.01")
    assert ReceiptItem(quantity=Decimal("0.333"), price=Decimal("3")).amount == Decimal("1.00")


def test_receipt_total():
    receipt = Receipt(
        items=[
            ReceiptItem(quantity=Decimal("10"), price=Decimal("450.50")),
            ReceiptItem(quantity=Decimal("2.5"), price=Decimal("100")),
        ]
    )
    assert receipt.total == Decimal("4755.00")


def test_empty_receipt_total_is_zero():
    assert Receipt(items=[]).total == Decimal("0.00")


@pytest.mark.parametrize(
    ("typed", "expected"), [("10,5", "10.5"), (" 1 000 ", "1000"), ("7", "7"), ("", "")]
)
def test_decimal_input_accepts_comma_and_spaces(typed, expected):
    assert decimal_input(typed) == expected


def test_validation_messages_are_in_russian():
    try:
        ReceiptItemIn(material_id=1, quantity="0", price="abc")
    except ValidationError as exc:
        errors = field_errors(exc.errors())
    assert errors == {"quantity": "Значение должно быть больше 0", "price": "Нужно число"}


def test_unknown_error_type_keeps_original_text():
    error = {"type": "something_new", "msg": "Original message", "ctx": {}}
    assert error_message(error) == "Original message"


def test_password_hash_and_check():
    password_hash = hash_password("secret123")
    assert password_hash != "secret123"
    assert verify_password("secret123", password_hash)
    assert not verify_password("secret124", password_hash)


def test_too_long_password_is_rejected_without_error():
    # bcrypt учитывает только 72 байта, более длинный пароль не принимается
    assert not verify_password("x" * 73, hash_password("x" * 72))


@pytest.mark.parametrize(
    ("value", "expected"),
    [(Decimal("40.000"), "40"), (Decimal("2.500"), "2.5"), (Decimal("0"), "0"), (None, "")],
)
def test_format_number(value, expected):
    assert format_number(value) == expected


def test_format_money():
    assert format_money(Decimal("67000")) == "67 000.00"
    assert format_money(None) == ""
