"""Append-only SHA-256 chained audit ledger."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any


def _hash_blob(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_last_hash(ledger_path: str) -> str:
    """Read the last entry's hash from the ledger file; return '' for empty file."""
    if not os.path.exists(ledger_path):
        return ""
    with open(ledger_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "hash" in entry:
                return str(entry["hash"])
    return ""


def append_entry(
    ledger_path: str,
    artifact_id: str,
    verdict: str,
    details: dict[str, Any],
    now: str | None = None,
) -> dict[str, Any]:
    """Append a single hash-chained entry to the ledger.

    The entry is written as one JSON line (JSON Lines format) so the ledger
    remains human-readable and append-only.
    """
    prev_hash = read_last_hash(ledger_path)
    entry: dict[str, Any] = {
        "timestamp": now or _now_iso(),
        "artifact_id": artifact_id,
        "verdict": verdict,
        "prev_hash": prev_hash,
        "details": details,
    }
    # Hash the entry *without* the hash field itself.
    canonical = json.dumps(entry, sort_keys=True, ensure_ascii=False)
    entry["hash"] = _hash_blob(canonical.encode("utf-8"))

    with open(ledger_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return entry


def verify_chain(ledger_path: str) -> dict[str, Any]:
    """Verify the integrity of the hash chain.

    Returns a dict with ok=True/False, the number of entries checked, and the
    first broken artifact_id if any.
    """
    if not os.path.exists(ledger_path):
        return {"ok": True, "checked": 0, "broken": None}

    expected_prev = ""
    checked = 0
    with open(ledger_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            stored_hash = entry.pop("hash", None)
            canonical = json.dumps(entry, sort_keys=True, ensure_ascii=False)
            computed_hash = _hash_blob(canonical.encode("utf-8"))
            if stored_hash != computed_hash:
                return {"ok": False, "checked": checked, "broken": entry.get("artifact_id")}
            if entry.get("prev_hash", "") != expected_prev:
                return {"ok": False, "checked": checked, "broken": entry.get("artifact_id")}
            expected_prev = stored_hash
            checked += 1

    return {"ok": True, "checked": checked, "broken": None}
