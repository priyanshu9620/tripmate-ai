"""In-process booking ledger. Idempotent: the same (item, travellers) always yields the same reference."""

import hashlib
from datetime import UTC, datetime

_LEDGER: dict[str, dict] = {}


def reference(kind: str, item_id: str, names: list[str]) -> str:
    raw = f"{kind}|{item_id}|{'|'.join(sorted(n.strip().lower() for n in names))}"
    return hashlib.sha1(raw.encode()).hexdigest()[:6].upper()


def record(kind: str, item_id: str, names: list[str], details: dict) -> dict:
    ref = reference(kind, item_id, names)
    if ref not in _LEDGER:
        _LEDGER[ref] = {
            "reference": ref,
            "kind": kind,
            "item_id": item_id,
            "travellers": names,
            "booked_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "already_booked": False,
            **details,
        }
        return _LEDGER[ref]
    return {**_LEDGER[ref], "already_booked": True}


def all_bookings() -> list[dict]:
    return list(_LEDGER.values())


def reset() -> None:
    _LEDGER.clear()
