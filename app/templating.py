from decimal import Decimal
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def flash(request: Request, message: str, category: str = "ok"):
    request.session.setdefault("flash", []).append([category, message])


def pop_flashes(request: Request):
    return request.session.pop("flash", [])


def format_number(value: Decimal | None) -> str:
    if value is None:
        return ""
    text = f"{value:f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def format_money(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"{value:,.2f}".replace(",", " ")


templates.env.globals["pop_flashes"] = pop_flashes
templates.env.filters["num"] = format_number
templates.env.filters["money"] = format_money
