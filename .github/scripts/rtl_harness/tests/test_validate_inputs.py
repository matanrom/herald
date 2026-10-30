#!/usr/bin/env python3
"""Negative tests for the dispatch-input validator (no Gradle, no network)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import validate_inputs  # noqa: E402

SAFE_SHA = "2073b3b07865376fd0b781ba62ebbf55267c46ff"

# Inputs an operator might paste (or an attacker might submit). None may reach a
# shell, and none may be echoed verbatim into the log.
MALICIOUS = [
    "$(printf RTL_INPUT_EXECUTED)",
    "`printf RTL_INPUT_EXECUTED`",
    "2073b3b07865376fd0b781ba62ebbf55267c46ff; id",
    "2073b3b07865376fd0b781ba62ebbf55267c46ff && id",
    "2073b3b07865376fd0b781ba62ebbf55267c46ff|id",
    "2073b3b07865376fd0b781ba62ebbf55267c46ff\nid",
    "$(id)\n2073b3b07865376fd0b781ba62ebbf55267c46ff",
    "../../etc/passwd",
    "HEAD~1",
    "main",
    "2073b3b0",
    "2073b3b07865376fd0b781ba62ebbf55267c46f",
    "2073b3b07865376fd0b781ba62ebbf55267c46fg",
    "2073B3B07865376FD0B781BA62EBbf55267c46ff",
    "--upload-pack=/bin/sh",
    "-c",
]


class MaliciousRevisionRejected(unittest.TestCase):
    def test_malicious_and_malformed_values_are_rejected(self) -> None:
        for value in MALICIOUS:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_inputs.resolve_revision("RED", value)

    def test_rejection_message_never_echoes_the_value(self) -> None:
        value = "$(printf RTL_INPUT_EXECUTED)"
        with self.assertRaises(ValueError) as caught:
            validate_inputs.resolve_revision("RED", value)
        self.assertNotIn("RTL_INPUT_EXECUTED", str(caught.exception))

    def test_full_commit_id_is_accepted_verbatim(self) -> None:
        self.assertEqual(validate_inputs.resolve_revision("RED", SAFE_SHA), SAFE_SHA)

    def test_red_requires_a_revision(self) -> None:
        with self.assertRaises(ValueError):
            validate_inputs.resolve_revision("RED", "")

    def test_green_refuses_a_production_substitution(self) -> None:
        with self.assertRaises(ValueError):
            validate_inputs.resolve_revision("GREEN", SAFE_SHA)


class ModeValidation(unittest.TestCase):
    def test_absent_input_defaults_to_green(self) -> None:
        self.assertEqual(validate_inputs.resolve_mode("", "push"), "GREEN")

    def test_explicit_modes_are_accepted(self) -> None:
        self.assertEqual(validate_inputs.resolve_mode("GREEN", "workflow_dispatch"), "GREEN")
        self.assertEqual(validate_inputs.resolve_mode("RED", "workflow_dispatch"), "RED")

    def test_unknown_mode_is_rejected(self) -> None:
        for value in ("green", "Green", "FAIL", "GREEN; id", "$(id)", "RED\nGREEN"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_inputs.resolve_mode(value, "workflow_dispatch")

    def test_red_requires_manual_dispatch(self) -> None:
        with self.assertRaises(ValueError):
            validate_inputs.resolve_mode("RED", "push")


class CliContract(unittest.TestCase):
    def test_green_push_writes_outputs_and_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "output"
            code = validate_inputs.main(
                ["--expected-result", "", "--production-revision", "", "--event-name", "push",
                 "--github-output", str(out)]
            )
            self.assertEqual(code, 0)
            text = out.read_text()
            self.assertIn("mode=GREEN", text)
            self.assertIn("production_revision=\n", text)

    def test_malicious_input_exits_nonzero_without_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "output"
            code = validate_inputs.main(
                ["--expected-result", "RED",
                 "--production-revision", "$(printf RTL_INPUT_EXECUTED)",
                 "--event-name", "workflow_dispatch", "--github-output", str(out)]
            )
            self.assertEqual(code, 1)
            self.assertFalse(out.exists())

    def test_red_dispatch_writes_the_validated_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "output"
            code = validate_inputs.main(
                ["--expected-result", "RED", "--production-revision", SAFE_SHA,
                 "--event-name", "workflow_dispatch", "--github-output", str(out)]
            )
            self.assertEqual(code, 0)
            self.assertIn(f"production_revision={SAFE_SHA}", out.read_text())


if __name__ == "__main__":
    unittest.main()
