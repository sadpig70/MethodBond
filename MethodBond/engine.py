"""Deterministic trust-bundle evaluator for method/model artifacts.

Verdict path:
    certified   -> license valid, reproducible, baseline clean
    conditional -> license+repro OK but a recoverable cert issue
    rejected    -> invalid license, unreproducible, or unacceptable cert drift
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


ALLOWED_TRANSFER_TYPES = {"exclusive", "non-exclusive", "permissive", "copyleft"}
ALLOWED_SOURCE_DOMAINS = {"academia", "industry", "government", "open", "unknown"}
ALLOWED_TARGET_INDUSTRIES = {"health", "finance", "energy", "education", "general", "unknown"}

REQUIRED_LICENSE_FIELDS = {
    "transfer_type",
    "source_domain",
    "target_industry",
    "revenue_share_pct",
}

REQUIRED_PROVENANCE_FIELDS = {"input_hash", "output_hash", "build_command", "builder_id"}
REQUIRED_POLICY_FIELDS = {"rules"}


def _hash_blob(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def evaluate(artifact: dict[str, Any]) -> dict[str, Any]:
    """Evaluate an artifact descriptor and return a verdict document."""
    license_ok, license_detail = _check_license(artifact.get("license", {}))
    repro_ok, repro_detail = _check_reproducibility(artifact.get("provenances", []))
    cert_ok, cert_detail = _check_certification(
        artifact.get("baseline_policy", {}),
        artifact.get("candidate_policy", {}),
    )

    details = {
        "license": license_detail,
        "reproducibility": repro_detail,
        "certification": cert_detail,
    }

    verdict = _compose_verdict(license_ok, repro_ok, cert_ok, details)

    return {
        "verdict": verdict,
        "artifact_id": artifact.get("id", "unknown"),
        "details": details,
    }


def _check_license(license_doc: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Validate MLX-style license metadata."""
    detail: dict[str, Any] = {"fields_present": [], "fields_missing": [], "errors": []}

    if not isinstance(license_doc, dict):
        detail["errors"].append("license block must be an object")
        return False, detail

    present = REQUIRED_LICENSE_FIELDS & set(license_doc.keys())
    missing = REQUIRED_LICENSE_FIELDS - present
    detail["fields_present"] = sorted(present)
    detail["fields_missing"] = sorted(missing)

    if missing:
        detail["errors"].append(f"missing required fields: {sorted(missing)}")

    transfer = license_doc.get("transfer_type")
    if transfer is not None and transfer not in ALLOWED_TRANSFER_TYPES:
        detail["errors"].append(f"transfer_type '{transfer}' not in allowed set")

    source = license_doc.get("source_domain")
    if source is not None and source not in ALLOWED_SOURCE_DOMAINS:
        detail["errors"].append(f"source_domain '{source}' not in allowed set")

    target = license_doc.get("target_industry")
    if target is not None and target not in ALLOWED_TARGET_INDUSTRIES:
        detail["errors"].append(f"target_industry '{target}' not in allowed set")

    revenue = license_doc.get("revenue_share_pct")
    if revenue is not None:
        try:
            revenue_val = float(revenue)
            if not (0.0 <= revenue_val <= 100.0):
                detail["errors"].append("revenue_share_pct must be between 0 and 100")
        except (TypeError, ValueError):
            detail["errors"].append("revenue_share_pct must be numeric")

    return (len(detail["errors"]) == 0), detail


def _check_reproducibility(provenances: list[Any]) -> tuple[bool, dict[str, Any]]:
    """Validate ReproDossier-style cross-provenance reproducibility."""
    detail: dict[str, Any] = {"provenance_count": 0, "errors": [], "output_hashes": []}

    if not isinstance(provenances, list):
        detail["errors"].append("provenances must be a list")
        return False, detail

    detail["provenance_count"] = len(provenances)
    if len(provenances) < 2:
        detail["errors"].append("at least two independent provenances are required")
        return False, detail

    output_hashes: list[str] = []
    for idx, prov in enumerate(provenances):
        prefix = f"provenance[{idx}]"
        if not isinstance(prov, dict):
            detail["errors"].append(f"{prefix} must be an object")
            continue

        missing = REQUIRED_PROVENANCE_FIELDS - set(prov.keys())
        if missing:
            detail["errors"].append(f"{prefix} missing fields: {sorted(missing)}")

        output_hash = prov.get("output_hash")
        if output_hash is not None:
            output_hashes.append(str(output_hash))

    detail["output_hashes"] = output_hashes

    if len(output_hashes) < 2:
        detail["errors"].append("insufficient output hashes to compare")
        return False, detail

    if len(set(output_hashes)) != 1:
        detail["errors"].append("output hashes do not match across provenances")
        return False, detail

    if detail["errors"]:
        return False, detail
    return True, detail


def _check_certification(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    """Validate CertMesh-style baseline-vs-candidate policy conformance."""
    detail: dict[str, Any] = {"baseline_rules": 0, "candidate_rules": 0, "drifts": []}

    if not isinstance(baseline, dict) or not isinstance(candidate, dict):
        detail["drifts"].append("baseline_policy and candidate_policy must be objects")
        return False, detail

    baseline_rules = baseline.get("rules", {})
    candidate_rules = candidate.get("rules", {})

    if not isinstance(baseline_rules, dict) or not isinstance(candidate_rules, dict):
        detail["drifts"].append("policy.rules must be objects")
        return False, detail

    detail["baseline_rules"] = len(baseline_rules)
    detail["candidate_rules"] = len(candidate_rules)

    if not baseline_rules:
        detail["drifts"].append("baseline policy has no rules")
        return False, detail

    recoverable = True
    for key, base_val in baseline_rules.items():
        cand_val = candidate_rules.get(key)
        if cand_val is None:
            detail["drifts"].append(f"missing rule '{key}' in candidate")
            recoverable = False
            continue
        if cand_val != base_val:
            detail["drifts"].append(
                f"rule '{key}' drift: baseline={base_val!r} candidate={cand_val!r}"
            )
            # Tightening the baseline (candidate stricter) is recoverable;
            # loosening is not.
            try:
                if float(cand_val) < float(base_val):
                    recoverable = False
            except (TypeError, ValueError):
                recoverable = False

    # Extra candidate rules not in baseline are considered recoverable extensions.
    for key in candidate_rules:
        if key not in baseline_rules:
            detail["drifts"].append(f"extra rule '{key}' in candidate (recoverable)")

    ok = len(detail["drifts"]) == 0
    return ok, detail


def _compose_verdict(
    license_ok: bool,
    repro_ok: bool,
    cert_ok: bool,
    details: dict[str, Any],
) -> str:
    if license_ok and repro_ok and cert_ok:
        return "certified"
    if not license_ok or not repro_ok:
        return "rejected"
    # License and reproducibility pass, but certification has only recoverable drift.
    return "conditional"


def hash_artifact(artifact: dict[str, Any]) -> str:
    """Return a stable SHA-256 fingerprint of the artifact descriptor."""
    canonical = json.dumps(artifact, sort_keys=True, ensure_ascii=False)
    return _hash_blob(canonical.encode("utf-8"))
