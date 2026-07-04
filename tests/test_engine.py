"""Unit tests for MethodBond engine verdict path."""

import unittest

from MethodBond.engine import (
    _check_certification,
    _check_license,
    _check_reproducibility,
    _compose_verdict,
    evaluate,
    hash_artifact,
)


class LicenseCheckTests(unittest.TestCase):
    def test_valid_license(self):
        ok, detail = _check_license(
            {
                "transfer_type": "permissive",
                "source_domain": "academia",
                "target_industry": "general",
                "revenue_share_pct": 0.0,
            }
        )
        self.assertTrue(ok)
        self.assertEqual(detail["errors"], [])

    def test_missing_field(self):
        ok, detail = _check_license({"transfer_type": "permissive"})
        self.assertFalse(ok)
        self.assertIn("missing required fields", detail["errors"][0])

    def test_invalid_transfer_type(self):
        ok, detail = _check_license(
            {
                "transfer_type": "proprietary",
                "source_domain": "industry",
                "target_industry": "finance",
                "revenue_share_pct": 5.0,
            }
        )
        self.assertFalse(ok)
        self.assertTrue(any("transfer_type" in e for e in detail["errors"]))

    def test_invalid_source_domain(self):
        ok, detail = _check_license(
            {
                "transfer_type": "exclusive",
                "source_domain": "military",
                "target_industry": "energy",
                "revenue_share_pct": 10.0,
            }
        )
        self.assertFalse(ok)
        self.assertTrue(any("source_domain" in e for e in detail["errors"]))

    def test_revenue_out_of_range(self):
        ok, detail = _check_license(
            {
                "transfer_type": "non-exclusive",
                "source_domain": "open",
                "target_industry": "education",
                "revenue_share_pct": 150.0,
            }
        )
        self.assertFalse(ok)
        self.assertTrue(any("revenue_share_pct" in e for e in detail["errors"]))

    def test_non_numeric_revenue(self):
        ok, detail = _check_license(
            {
                "transfer_type": "copyleft",
                "source_domain": "open",
                "target_industry": "unknown",
                "revenue_share_pct": "free",
            }
        )
        self.assertFalse(ok)
        self.assertTrue(any("revenue_share_pct" in e for e in detail["errors"]))

    def test_license_not_dict(self):
        ok, detail = _check_license("bad")
        self.assertFalse(ok)
        self.assertIn("license block must be an object", detail["errors"])


class ReproducibilityCheckTests(unittest.TestCase):
    def test_valid_repro(self):
        provs = [
            {
                "input_hash": "sha256:a",
                "output_hash": "sha256:b",
                "build_command": "make",
                "builder_id": "x",
            },
            {
                "input_hash": "sha256:a",
                "output_hash": "sha256:b",
                "build_command": "make",
                "builder_id": "y",
            },
        ]
        ok, detail = _check_reproducibility(provs)
        self.assertTrue(ok)
        self.assertEqual(detail["errors"], [])

    def test_too_few_provenances(self):
        ok, detail = _check_reproducibility([{"output_hash": "sha256:b"}])
        self.assertFalse(ok)
        self.assertIn("at least two independent provenances are required", detail["errors"])

    def test_mismatched_outputs(self):
        provs = [
            {"output_hash": "sha256:a", "input_hash": "i", "build_command": "c", "builder_id": "x"},
            {"output_hash": "sha256:b", "input_hash": "i", "build_command": "c", "builder_id": "y"},
        ]
        ok, detail = _check_reproducibility(provs)
        self.assertFalse(ok)
        self.assertIn("output hashes do not match across provenances", detail["errors"])

    def test_missing_provenance_fields(self):
        provs = [
            {"output_hash": "sha256:a"},
            {"output_hash": "sha256:a"},
        ]
        ok, detail = _check_reproducibility(provs)
        self.assertFalse(ok)
        self.assertTrue(any("missing fields" in e for e in detail["errors"]))

    def test_provenances_not_list(self):
        ok, detail = _check_reproducibility({})
        self.assertFalse(ok)
        self.assertIn("provenances must be a list", detail["errors"])


class CertificationCheckTests(unittest.TestCase):
    def test_clean_baseline(self):
        baseline = {"rules": {"latency": 100}}
        candidate = {"rules": {"latency": 100}}
        ok, detail = _check_certification(baseline, candidate)
        self.assertTrue(ok)
        self.assertEqual(detail["drifts"], [])

    def test_tightening_is_recoverable(self):
        baseline = {"rules": {"latency": 100}}
        candidate = {"rules": {"latency": 50}}
        ok, detail = _check_certification(baseline, candidate)
        self.assertFalse(ok)
        self.assertTrue(any("latency" in d for d in detail["drifts"]))

    def test_loosening_is_not_recoverable(self):
        baseline = {"rules": {"latency": 100}}
        candidate = {"rules": {"latency": 200}}
        ok, detail = _check_certification(baseline, candidate)
        self.assertFalse(ok)
        self.assertTrue(any("latency" in d for d in detail["drifts"]))

    def test_missing_candidate_rule(self):
        baseline = {"rules": {"latency": 100, "audit": True}}
        candidate = {"rules": {"latency": 100}}
        ok, detail = _check_certification(baseline, candidate)
        self.assertFalse(ok)
        self.assertTrue(any("missing rule 'audit'" in d for d in detail["drifts"]))

    def test_empty_baseline(self):
        ok, detail = _check_certification({"rules": {}}, {"rules": {"x": 1}})
        self.assertFalse(ok)
        self.assertIn("baseline policy has no rules", detail["drifts"])


class ComposeVerdictTests(unittest.TestCase):
    def test_certified(self):
        self.assertEqual(_compose_verdict(True, True, True, {}), "certified")

    def test_rejected_on_license(self):
        self.assertEqual(_compose_verdict(False, True, True, {}), "rejected")

    def test_rejected_on_repro(self):
        self.assertEqual(_compose_verdict(True, False, True, {}), "rejected")

    def test_conditional_on_cert(self):
        self.assertEqual(_compose_verdict(True, True, False, {}), "conditional")


class EvaluateIntegrationTests(unittest.TestCase):
    def make_artifact(self, **overrides):
        artifact = {
            "id": "test-artifact",
            "license": {
                "transfer_type": "permissive",
                "source_domain": "academia",
                "target_industry": "general",
                "revenue_share_pct": 0.0,
            },
            "provenances": [
                {
                    "input_hash": "sha256:in",
                    "output_hash": "sha256:out",
                    "build_command": "python run.py",
                    "builder_id": "a",
                },
                {
                    "input_hash": "sha256:in",
                    "output_hash": "sha256:out",
                    "build_command": "python run.py",
                    "builder_id": "b",
                },
            ],
            "baseline_policy": {"rules": {"max_latency": 100}},
            "candidate_policy": {"rules": {"max_latency": 100}},
        }
        artifact.update(overrides)
        return artifact

    def test_certified(self):
        result = evaluate(self.make_artifact())
        self.assertEqual(result["verdict"], "certified")

    def test_rejected_bad_license(self):
        result = evaluate(self.make_artifact(license={"transfer_type": "bad"}))
        self.assertEqual(result["verdict"], "rejected")

    def test_rejected_mismatched_hash(self):
        provenances = self.make_artifact()["provenances"]
        provenances[1]["output_hash"] = "sha256:other"
        result = evaluate(self.make_artifact(provenances=provenances))
        self.assertEqual(result["verdict"], "rejected")

    def test_conditional_cert_drift(self):
        result = evaluate(self.make_artifact(candidate_policy={"rules": {"max_latency": 50}}))
        self.assertEqual(result["verdict"], "conditional")

    def test_hash_artifact_stable(self):
        a = self.make_artifact()
        b = self.make_artifact()
        self.assertEqual(hash_artifact(a), hash_artifact(b))


if __name__ == "__main__":
    unittest.main()
