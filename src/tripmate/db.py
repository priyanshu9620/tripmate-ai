"""Postgres access. Phase 0 pings it for /healthz; Phase 2 adds checkpointer, store and trips table."""

import psycopg

from tripmate.config import settings


def ping(timeout_s: float = 2.0) -> bool:
    try:
        with psycopg.connect(settings.database_url, connect_timeout=timeout_s) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False
