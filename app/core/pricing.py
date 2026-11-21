"""Exact pricing for Food4Thought cart views and historical order snapshots.
Callers supply canonical two-decimal amounts and validated quantities.
"""

from collections.abc import Iterable
from decimal import Decimal
from typing import Annotated

from pydantic import StringConstraints

Money = Annotated[str, StringConstraints(pattern=r"^(0|[1-9][0-9]*)\.[0-9]{2}$")]


def cents(amount: str) -> int:
    """Read validated money exactly, even when a total exceeds int's text limit."""
    return int(Decimal(amount.replace(".", "")))


def money(amount_in_cents: int) -> str:
    whole, fraction = divmod(amount_in_cents, 100)
    # Decimal converts the integer exactly without rounding to context precision.
    return f"{Decimal(whole):f}.{fraction:02d}"


def line_total(unit_price: str, quantity: int) -> str:
    return money(cents(unit_price) * quantity)


def sum_line_totals(amounts: Iterable[str]) -> str:
    return money(sum(cents(amount) for amount in amounts))
