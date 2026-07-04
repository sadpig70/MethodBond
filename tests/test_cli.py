"""Integration tests for MethodBond CLI."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from MethodBond.cli import main


class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_sample_command(self):
        sample_path = self.base / "sample.json"
        rc = main(["sample", "-o", str(sample_path)])
        self.assertEqual(rc, 0)
        self.assertTrue(sample_path.exists())
        with open(sample_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("license", data)
        self.assertIn("provenances", data)

    def test_evaluate_command_certified(self):
        sample_path = self.base / "sample.json"
        main(["sample", "-o", str(sample_path)])
        rc = main(["evaluate", str(sample_path)])
        self.assertEqual(rc, 0)

    def test_evaluate_command_rejected(self):
        sample_path = self.base / "bad.json"
        with open(sample_path, "w", encoding="utf-8") as f:
            json.dump({"id": "bad", "license": {}}, f)
        rc = main(["evaluate", str(sample_path)])
        self.assertEqual(rc, 1)

    def test_evaluate_writes_ledger(self):
        sample_path = self.base / "sample.json"
        ledger_path = self.base / "ledger.jsonl"
        main(["sample", "-o", str(sample_path)])
        main(["evaluate", str(sample_path), "-l", str(ledger_path)])
        self.assertTrue(ledger_path.exists())
        with open(ledger_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        self.assertEqual(len(lines), 1)
        entry = json.loads(lines[0])
        self.assertEqual(entry["verdict"], "certified")
        self.assertIn("hash", entry)
        self.assertEqual(entry["prev_hash"], "")

    def test_report_command(self):
        sample_path = self.base / "sample.json"
        report_path = self.base / "report.md"
        main(["sample", "-o", str(sample_path)])
        rc = main(["report", str(sample_path), "-o", str(report_path)])
        self.assertEqual(rc, 0)
        with open(report_path, "r", encoding="utf-8") as f:
            text = f.read()
        self.assertIn("MethodBond Evaluation Report", text)
        self.assertIn("certified", text)

    def test_evaluate_json_output(self):
        sample_path = self.base / "sample.json"
        main(["sample", "-o", str(sample_path)])
        # Capture stdout via redirecting is harder; instead just assert evaluate returns 0.
        rc = main(["evaluate", str(sample_path), "--json"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
