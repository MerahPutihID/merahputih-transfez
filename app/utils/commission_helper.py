"""
Commission Helper
-----------------
Runs the recursive customer-hierarchy query for a CDM transaction and persists
the resulting commission rows into cdt_commision.
"""

import logging
from sqlalchemy import text

from app.models import Commission

logger = logging.getLogger(__name__)

# COMMISSION_HIERARCHY_SQL = text(
#     """
#     WITH RECURSIVE customer_hierarchy AS (
#         -- Anchor: customer dari transaksi CDM + commission rate yang berlaku
#         SELECT
#             cc.id,
#             cc.name,
#             cc.parent_id,
#             1 AS level,
#             macr.commission_type::varchar,
#             macr.commission_rate::numeric,
#             macr.rate_type::varchar,
#             ctc.cdm_trx_datetime::timestamp AS cdm_trx_datetime
#         FROM public.cdt_trx_cdm ctc
#         JOIN public.cdt_machine cm ON ctc.machine_id = cm.id
#         JOIN public.cdt_customer cc ON cm.customer_id = cc.id
#         JOIN custmp.m_account ma ON ma.uuid_be = cc.id::text
#         JOIN custmp.m_account_commission_rate macr ON ma.id = macr.account_id
#         WHERE ctc.id = CAST(:cdt_trx_cdm_id AS uuid)
#           AND macr.is_active = true
#           AND macr.active_date <= ctc.cdm_trx_datetime
#           AND (macr.terminate_date IS NULL OR macr.terminate_date > ctc.cdm_trx_datetime)

#         UNION ALL

#         -- Recursive: naik ke PARENT
#         SELECT
#             parent.id,
#             parent.name,
#             parent.parent_id,
#             child.level + 1 AS level,
#             macr.commission_type::varchar,
#             macr.commission_rate::numeric,
#             macr.rate_type::varchar,
#             child.cdm_trx_datetime::timestamp AS cdm_trx_datetime
#         FROM public.cdt_customer parent
#         INNER JOIN customer_hierarchy child ON parent.id = child.parent_id
#         LEFT JOIN custmp.m_account ma ON ma.uuid_be = parent.id::text
#         LEFT JOIN custmp.m_account_commission_rate macr
#             ON ma.id = macr.account_id
#             AND macr.is_active = true
#             AND macr.active_date <= child.cdm_trx_datetime
#             AND (macr.terminate_date IS NULL OR macr.terminate_date > child.cdm_trx_datetime)
#     )
#     SELECT id AS customer_id, commission_type, commission_rate, rate_type
#     FROM customer_hierarchy
#     WHERE commission_type IS NOT NULL
#     ORDER BY level
#     """
# )

COMMISSION_HIERARCHY_SQL = text(
    """
        SELECT
            gch.id AS customer_id,
            gch.commission_type,
            gch.commission_rate,
            gch.rate_type,
            gch.level
        FROM get_commission_hierarchy(CAST(:cdt_trx_cdm_id AS uuid)) gch
        ORDER BY gch.level
    """
)

def record_commissions(db, cdt_trx_cdm_id) -> int:
    """Run the commission hierarchy query for one CDM transaction and persist the rows.

    Idempotent: if rows already exist for this cdt_trx_cdm_id, nothing is written
    (retries reuse the original snapshot).

    Never raises: a commission failure is logged and the return value is 0, so a
    snapshot problem cannot roll back or abort the transfer itself.

    Returns:
        int: number of commission rows written.
    """
    try:
        existing = (
            db.query(Commission.id)
            .filter(Commission.cdt_trx_cdm_id == cdt_trx_cdm_id)
            .first()
        )
        if existing:
            logger.info(
                "Commission rows already exist for cdt_trx_cdm_id=%s - skipping",
                cdt_trx_cdm_id,
            )
            return 0

        rows = (
            db.execute(
                COMMISSION_HIERARCHY_SQL, {"cdt_trx_cdm_id": str(cdt_trx_cdm_id)}
            )
            .mappings()
            .all()
        )

        if not rows:
            logger.info("No active commission rows for cdt_trx_cdm_id=%s", cdt_trx_cdm_id)
            return 0

        db.add_all(
            [
                Commission(
                    cdt_trx_cdm_id=cdt_trx_cdm_id,
                    customer_id=row["customer_id"],
                    commission_type=row["commission_type"],
                    commission_rate=row["commission_rate"],
                    rate_type=row["rate_type"],
                )
                for row in rows
            ]
        )
        db.commit()
        logger.info(
            "Stored %s commission rows for cdt_trx_cdm_id=%s", len(rows), cdt_trx_cdm_id
        )
        return len(rows)
    except Exception as e:
        db.rollback()
        logger.error(
            "Failed to record commission rows for cdt_trx_cdm_id=%s: %s",
            cdt_trx_cdm_id,
            e,
        )
        return 0
