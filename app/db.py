import os
import uuid
import asyncio
import logging
from databricks.sdk import WorkspaceClient
import psycopg
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)

APP_SCHEMA = "app_data"
_pool = None


def _get_instance_name() -> str:
    """Return the Lakebase instance name for credential generation.

    Uses LAKEBASE_INSTANCE_NAME if set, otherwise falls back to PGAPPNAME
    (which Databricks Apps sets to the app name). Override with
    LAKEBASE_INSTANCE_NAME if your instance name differs from the app name.
    """
    name = os.environ.get("LAKEBASE_INSTANCE_NAME") or os.environ.get("PGAPPNAME")
    if not name:
        raise RuntimeError(
            "Cannot determine Lakebase instance name. "
            "Set LAKEBASE_INSTANCE_NAME in your .env file or app.yaml."
        )
    return name


class RotatingTokenConnection(psycopg.Connection):
    """psycopg Connection subclass that fetches a fresh Databricks token on each connect."""

    @classmethod
    def connect(cls, conninfo: str = "", **kwargs):
        w = WorkspaceClient()
        kwargs["password"] = w.database.generate_database_credential(
            request_id=str(uuid.uuid4()),
            instance_names=[_get_instance_name()],
        ).token
        kwargs.setdefault("sslmode", "require")
        return super().connect(conninfo, **kwargs)


def _configure_connection(conn: psycopg.Connection) -> None:
    """Set search_path on each new pool connection.

    This ensures all unqualified table names resolve to the app's own schema
    without requiring ``CREATE`` privileges on the ``public`` schema.
    """
    conn.execute(f"SET search_path TO {APP_SCHEMA}, public")
    conn.commit()


def get_pool() -> ConnectionPool:
    """Return (and lazily create) the shared connection pool.

    Expects PG* environment variables (PGHOST, PGDATABASE, PGPORT, etc.)
    to be set — either manually for local development or automatically by
    Databricks Apps when a Lakebase database resource is attached.
    """
    global _pool
    if _pool is None:
        if not os.environ.get("PGHOST"):
            raise RuntimeError(
                "PGHOST environment variable is not set. "
                "Add a Lakebase database instance as a resource to your Databricks App. "
                "See: https://docs.databricks.com/aws/en/dev-tools/databricks-apps/lakebase"
            )
        if not os.environ.get("PGUSER"):
            w = WorkspaceClient()
            os.environ["PGUSER"] = w.current_user.me().user_name
        _pool = ConnectionPool(
            conninfo="",
            connection_class=RotatingTokenConnection,
            configure=_configure_connection,
            min_size=1,
            max_size=5,
            open=True,
        )
    return _pool


def ensure_schema() -> None:
    """Create application schema and tables if they do not already exist.

    Uses a dedicated schema (``app_data``) so the app works out of the box
    even when the database role lacks ``CREATE`` privileges on the ``public``
    schema.  The pool's ``search_path`` is set to ``app_data, public`` so all
    queries using unqualified table names resolve correctly.
    """
    pool = get_pool()
    ddl = f"""
    CREATE SCHEMA IF NOT EXISTS {APP_SCHEMA};
    CREATE TABLE IF NOT EXISTS {APP_SCHEMA}.help_ticket (
        ticket_id TEXT,
        customer_id TEXT,
        subject TEXT,
        status TEXT,
        created_at TIMESTAMP,
        resolved_at TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS {APP_SCHEMA}.refund_requests (
        refund_id TEXT,
        ticket_id TEXT,
        payment_id TEXT,
        sku TEXT,
        request_date TIMESTAMP,
        approved BOOLEAN,
        approval_date TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS {APP_SCHEMA}.stripe_payments (
        payment_id TEXT,
        customer_id TEXT,
        amount_cents INTEGER,
        currency TEXT,
        payment_status TEXT,
        payment_date TIMESTAMP
    );
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
    logger.info("Database schema verified — tables are ready.")
    _seed_sample_data(pool)


def _seed_sample_data(pool: ConnectionPool) -> None:
    """Insert sample data into empty tables so the dashboard is populated on first run."""
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM help_ticket")
            if cur.fetchone()[0] > 0:
                logger.info("Tables already contain data — skipping seed.")
                return

            tickets = [
                ("TKT-001", "CUST-101", "Cannot log in to my account", "open", "2025-06-01 09:15:00", None),
                ("TKT-002", "CUST-102", "Billing discrepancy on invoice #4821", "pending", "2025-06-02 11:30:00", None),
                ("TKT-003", "CUST-103", "App crashes on checkout page", "resolved", "2025-05-28 14:00:00", "2025-06-01 10:00:00"),
                ("TKT-004", "CUST-104", "Request for feature: dark mode", "closed", "2025-05-20 08:45:00", "2025-05-25 16:30:00"),
                ("TKT-005", "CUST-105", "Shipping address not updating", "open", "2025-06-03 10:20:00", None),
                ("TKT-006", "CUST-101", "Two-factor authentication not working", "open", "2025-06-04 13:00:00", None),
                ("TKT-007", "CUST-106", "Received wrong item in order #7733", "pending", "2025-06-04 15:45:00", None),
                ("TKT-008", "CUST-107", "Subscription auto-renewed unexpectedly", "resolved", "2025-05-30 09:00:00", "2025-06-02 14:20:00"),
                ("TKT-009", "CUST-108", "Promo code SAVE20 not applying at checkout", "open", "2025-06-05 08:10:00", None),
                ("TKT-010", "CUST-109", "Account locked after password reset", "closed", "2025-05-15 11:00:00", "2025-05-16 09:30:00"),
                ("TKT-011", "CUST-110", "Missing order confirmation email", "pending", "2025-06-05 16:30:00", None),
                ("TKT-012", "CUST-102", "Duplicate charge on credit card", "open", "2025-06-06 10:00:00", None),
            ]
            cur.executemany(
                "INSERT INTO help_ticket (ticket_id, customer_id, subject, status, created_at, resolved_at) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                tickets,
            )

            payments = [
                ("PAY-001", "CUST-101", 4999, "USD", "succeeded", "2025-05-28 10:00:00"),
                ("PAY-002", "CUST-102", 12500, "USD", "succeeded", "2025-05-29 11:30:00"),
                ("PAY-003", "CUST-103", 7999, "USD", "succeeded", "2025-05-30 09:15:00"),
                ("PAY-004", "CUST-104", 3200, "USD", "failed", "2025-05-31 14:00:00"),
                ("PAY-005", "CUST-105", 15000, "USD", "succeeded", "2025-06-01 08:45:00"),
                ("PAY-006", "CUST-106", 6499, "USD", "pending", "2025-06-02 12:00:00"),
                ("PAY-007", "CUST-107", 8999, "USD", "succeeded", "2025-06-03 10:30:00"),
                ("PAY-008", "CUST-108", 2499, "USD", "refunded", "2025-06-03 16:00:00"),
                ("PAY-009", "CUST-109", 19999, "USD", "succeeded", "2025-06-04 09:00:00"),
                ("PAY-010", "CUST-110", 5500, "USD", "failed", "2025-06-05 11:20:00"),
            ]
            cur.executemany(
                "INSERT INTO stripe_payments (payment_id, customer_id, amount_cents, currency, payment_status, payment_date) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                payments,
            )

            refunds = [
                ("REF-001", "TKT-003", "PAY-003", "SKU-WIDGET-A", "2025-06-01 10:30:00", True, "2025-06-02 09:00:00"),
                ("REF-002", "TKT-002", "PAY-002", "SKU-GADGET-B", "2025-06-02 14:00:00", None, None),
                ("REF-003", "TKT-007", "PAY-007", "SKU-WIDGET-A", "2025-06-04 16:00:00", None, None),
                ("REF-004", "TKT-008", "PAY-008", "SKU-SERVICE-C", "2025-06-01 09:30:00", True, "2025-06-01 15:00:00"),
                ("REF-005", "TKT-004", "PAY-004", "SKU-GADGET-B", "2025-05-25 12:00:00", False, "2025-05-26 10:00:00"),
                ("REF-006", "TKT-012", "PAY-002", "SKU-PREMIUM-D", "2025-06-06 10:30:00", None, None),
                ("REF-007", "TKT-009", "PAY-009", "SKU-WIDGET-A", "2025-06-05 09:00:00", True, "2025-06-06 08:00:00"),
            ]
            cur.executemany(
                "INSERT INTO refund_requests (refund_id, ticket_id, payment_id, sku, request_date, approved, approval_date) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                refunds,
            )

    logger.info("Sample seed data inserted into empty tables.")


def _execute_sync(
    sql: str,
    params: dict[str, str | int | float | bool | None] | tuple | None = None,
    fetch: str | None = None,
) -> list[tuple] | tuple | None:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if fetch == "all":
                return cur.fetchall()
            elif fetch == "one":
                return cur.fetchone()
            else:
                return None


async def fetch_all(
    sql: str, params: dict[str, str | int | float | bool | None] | tuple | None = None
) -> list[tuple]:
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _execute_sync, sql, params, "all")
    return result if result is not None else []


async def fetch_one(
    sql: str, params: dict[str, str | int | float | bool | None] | tuple | None = None
) -> tuple | None:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _execute_sync, sql, params, "one")


async def execute(
    sql: str, params: dict[str, str | int | float | bool | None] | tuple | None = None
) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _execute_sync, sql, params, None)