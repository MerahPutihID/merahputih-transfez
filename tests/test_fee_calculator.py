"""Self-check for calculate_transaction_fee (single-tier match + VAT).

Run: python -m unittest tests.test_fee_calculator -v
"""
import unittest
from unittest import mock

from app.utils import fee_calculator


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeDb:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, query, params):
        return _FakeResult(self._rows)

    def close(self):
        pass


def patch_tiers(tier_rows):
    """Patch get_db so calculate_transaction_fee sees the given tier rows."""
    db = _FakeDb(tier_rows)
    return mock.patch.object(fee_calculator, "get_db", lambda: iter([db]))


# (tier_type, fee, min_amount, max_amount, vat) — same shape as the SELECT,
# sorted by min_amount DESC as the real query does.
TIERS_NOMINAL_VAT = [
    ("nominal", 20000, 100000001, None, 0),  # >100M, max NULL = unbounded
    ("nominal", 15000, 5000001, 100000000, 0),
    ("nominal", 10000, 1000001, 5000000, 11),  # VAT 11%
    ("nominal", 5000, 0, 1000000, 0),
]

TIERS_MIXED_PERCENT = [
    ("percentage", 0.10, 500000001, None, 0),  # >500M 0.10%
    ("percentage", 0.11, 100000001, 500000000, 0),  # 100M-500M 0.11%
    ("nominal", 15000, 5000001, 100000000, 0),
    ("nominal", 10000, 1000001, 5000000, 0),
    ("nominal", 5000, 0, 1000000, 0),
]


class FeeCalculatorTest(unittest.TestCase):
    def setUp(self):
        fee_calculator.settings.MAX_FEE_PERCENTAGE = 20

    def test_top_tier_not_cumulative(self):
        # Single-match: >100M tier wins outright, no rolling into lower tiers.
        with patch_tiers(TIERS_NOMINAL_VAT):
            r = fee_calculator.calculate_transaction_fee("c1", 103000000)
        self.assertEqual(r["deduction_amount"], 20000.0)
        self.assertEqual(r["deduction_amount_pre"], 20000.0)
        self.assertEqual(r["final_amount"], 103000000 - 20000)

        with patch_tiers(TIERS_NOMINAL_VAT):
            r = fee_calculator.calculate_transaction_fee("c1", 120000000)
        self.assertEqual(r["deduction_amount"], 20000.0)

    def test_nominal_below_top(self):
        with patch_tiers(TIERS_NOMINAL_VAT):
            r = fee_calculator.calculate_transaction_fee("c1", 50000000)
        self.assertEqual(r["deduction_amount"], 15000.0)

    def test_vat_applied_on_base_fee(self):
        # fee 10.000 * 11% = 1.100 -> final fee 11.100
        with patch_tiers(TIERS_NOMINAL_VAT):
            r = fee_calculator.calculate_transaction_fee("c1", 3000000)
        self.assertEqual(r["deduction_amount_pre"], 10000.0)
        self.assertEqual(r["vat"], 11.0)
        self.assertEqual(r["vat_amount"], 1100.0)
        self.assertEqual(r["deduction_amount"], 11100.0)
        self.assertEqual(r["final_amount"], 3000000 - 11100)

    def test_vat_zero_no_vat_amount(self):
        with patch_tiers(TIERS_NOMINAL_VAT):
            r = fee_calculator.calculate_transaction_fee("c1", 600000)
        self.assertEqual(r["deduction_amount"], 5000.0)
        self.assertEqual(r["vat"], 0.0)
        self.assertEqual(r["vat_amount"], 0.0)

    def test_percentage_tier(self):
        # 200M in the 0.11% tier -> 220.000
        with patch_tiers(TIERS_MIXED_PERCENT):
            r = fee_calculator.calculate_transaction_fee("c1", 200000000)
        self.assertEqual(r["deduction_amount"], 220000.0)
        self.assertEqual(r["deduction_amount_pre"], 220000.0)

        # 600M in the 0.10% tier -> 600.000
        with patch_tiers(TIERS_MIXED_PERCENT):
            r = fee_calculator.calculate_transaction_fee("c1", 600000000)
        self.assertEqual(r["deduction_amount"], 600000.0)

    def test_fee_capped_by_max_percentage(self):
        tiers = [("percentage", 50, 0, 1000000, 0)]
        with patch_tiers(tiers):
            r = fee_calculator.calculate_transaction_fee("c1", 100000)
        # 50% raw fee capped at MAX_FEE_PERCENTAGE=20% -> 20.000
        self.assertEqual(r["deduction_amount"], 20000.0)

    def test_no_tier_match_returns_zero(self):
        with patch_tiers([]):
            r = fee_calculator.calculate_transaction_fee("c1", 100000)
        self.assertEqual(r["deduction_amount"], 0.0)
        self.assertEqual(r["final_amount"], 100000)


if __name__ == "__main__":
    unittest.main()
