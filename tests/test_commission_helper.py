"""Self-check for record_commissions (insert, idempotency, failure isolation).

Run: python -m unittest tests.test_commission_helper -v
"""
import unittest
from uuid import uuid4

from app.utils import commission_helper


class _FakeMappings:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return _FakeMappings(self._rows)


class _FakeQuery:
    def __init__(self, existing):
        self._existing = existing

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._existing


class _FakeDb:
    """Minimal stand-in for a SQLAlchemy Session."""

    def __init__(self, rows, existing=None, execute_raises=False):
        self._rows = rows
        self._existing = existing
        self._execute_raises = execute_raises
        self.added = []
        self.committed = 0
        self.rolled_back = 0
        self.last_params = None

    def query(self, *args):
        return _FakeQuery(self._existing)

    def execute(self, query, params):
        self.last_params = params
        if self._execute_raises:
            raise RuntimeError("boom")
        return _FakeResult(self._rows)

    def add_all(self, objs):
        self.added.extend(objs)

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1


ROWS = [
    {"customer_id": uuid4(), "commission_type": "PERCENTAGE", "commission_rate": 1.50, "rate_type": "SHARING"},
    {"customer_id": uuid4(), "commission_type": "NOMINAL", "commission_rate": 500.00, "rate_type": None},
]


class RecordCommissionsTests(unittest.TestCase):
    def test_inserts_one_row_per_hierarchy_entry(self):
        trx_id = uuid4()
        db = _FakeDb(ROWS)

        count = commission_helper.record_commissions(db, trx_id)

        self.assertEqual(count, 2)
        self.assertEqual(len(db.added), 2)
        self.assertEqual(db.committed, 1)
        self.assertEqual(db.rolled_back, 0)
        for row in db.added:
            self.assertEqual(row.cdt_trx_cdm_id, trx_id)
        self.assertEqual([r.customer_id for r in db.added], [r["customer_id"] for r in ROWS])
        self.assertEqual([r.commission_type for r in db.added], ["PERCENTAGE", "NOMINAL"])

    def test_passes_transaction_id_as_string_bind(self):
        trx_id = uuid4()
        db = _FakeDb(ROWS)

        commission_helper.record_commissions(db, trx_id)

        self.assertEqual(db.last_params, {"cdt_trx_cdm_id": str(trx_id)})
        self.assertIn("CAST(:cdt_trx_cdm_id AS uuid)", commission_helper.COMMISSION_HIERARCHY_SQL.text)

    def test_skips_when_rows_already_exist(self):
        db = _FakeDb(ROWS, existing=uuid4())

        count = commission_helper.record_commissions(db, uuid4())

        self.assertEqual(count, 0)
        self.assertEqual(db.added, [])
        self.assertEqual(db.committed, 0)
        self.assertIsNone(db.last_params)

    def test_no_hierarchy_rows_writes_nothing(self):
        db = _FakeDb([])

        count = commission_helper.record_commissions(db, uuid4())

        self.assertEqual(count, 0)
        self.assertEqual(db.added, [])
        self.assertEqual(db.committed, 0)

    def test_query_failure_is_swallowed_and_rolled_back(self):
        db = _FakeDb(ROWS, execute_raises=True)

        count = commission_helper.record_commissions(db, uuid4())

        self.assertEqual(count, 0)
        self.assertEqual(db.rolled_back, 1)
        self.assertEqual(db.added, [])


if __name__ == "__main__":
    unittest.main()
