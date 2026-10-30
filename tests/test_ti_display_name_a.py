"""labels.display_name: merchant and institution names as a slide prints them (Sheila's 1798 slide
review, 2026-10-30: "Circlek", "Lowe'S", "Wal Mart", "Mountain America Cu" on the slides)."""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build"), str(REPO / "build" / "ars_pipeline")]
from ti.deck.labels import display_name  # noqa: E402


@pytest.mark.parametrize("raw, want", [
    ("CIRCLEK", "Circle K"), ("Circlek", "Circle K"), ("CIRCLE K", "Circle K"),
    ("WAL MART", "Walmart"), ("Wal Mart", "Walmart"), ("WALMART", "Walmart"), ("WAL-MART", "Walmart"),
    ("LOWES", "Lowe's"), ("Lowe'S", "Lowe's"), ("LOWE'S", "Lowe's"),
    ("MOUNTAIN AMERICA CU", "Mountain America CU"), ("Mountain America Cu", "Mountain America CU"),
    ("PAYPAL", "PayPal"), ("PayPal", "PayPal"),
    ("USAA", "USAA"), ("FIRSTLIGHT FCU", "Firstlight FCU"), ("Firstlight Fcu", "Firstlight FCU"),
    ("BANK OF AMERICA, N.A.", "Bank of America, N.A."), ("Bank Of America", "Bank of America"),
    ("SYNCHRONY BANK", "Synchrony Bank"), ("AFTERPAY BNPL", "Afterpay BNPL"), ("ATM WITHDRAWAL", "ATM Withdrawal"),
    ("ACME HOLDINGS LLC", "Acme Holdings LLC"), ("SAM'S CLUB", "Sam's Club"), ("O'REILLY AUTO", "O'Reilly Auto"),
    ("7-ELEVEN", "7-Eleven"), ("CVS PHARMACY", "CVS Pharmacy"),
    ("Flex Finance", "Flex Finance"), ("ABC Supply LLC", "ABC Supply LLC"),
    ("  cash   app ", "Cash App"), ("", ""), (None, ""),
])
def test_display_name(raw, want):
    assert display_name(raw) == want


@pytest.mark.parametrize("raw", ["CIRCLEK", "Lowe'S", "MOUNTAIN AMERICA CU", "BANK OF AMERICA, N.A.",
                                 "SAM'S CLUB", "PayPal", "eBay", "Flex Finance", "T-MOBILE"])
def test_display_name_is_idempotent(raw):
    once = display_name(raw)
    assert display_name(once) == once
