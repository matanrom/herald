#!/usr/bin/env python3
"""Negative tests for the fail-closed report gate (synthetic JUnit, no Gradle)."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_reports  # noqa: E402

DS = check_reports.DESIGNSYSTEM_SUITE
UI = check_reports.UI_SUITE
RED_FAILURES = {f"{suite}#{name}" for suite, names in check_reports.EXPECTED_FAILURES_WHEN_RED.items()
                for name in names}


def write_suite(directory: Path, filename: str, suite: str, cases: dict[str, str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    body = []
    for name, status in cases.items():
        if status == check_reports.FAILURE:
            inner = '<failure message="expected x but was y"/>'
        elif status == check_reports.ERROR:
            inner = "<error/>"
        elif status == check_reports.SKIP:
            inner = "<skipped/>"
        else:
            inner = ""
        body.append(f'<testcase classname="{escape(suite)}" name="{escape(name)}">{inner}</testcase>')
    failures = sum(1 for s in cases.values() if s == check_reports.FAILURE)
    errors = sum(1 for s in cases.values() if s == check_reports.ERROR)
    skipped = sum(1 for s in cases.values() if s == check_reports.SKIP)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<testsuite name="{escape(suite)}" tests="{len(cases)}" failures="{failures}" '
        f'errors="{errors}" skipped="{skipped}">' + "".join(body) + "</testsuite>"
    )
    (directory / filename).write_text(xml, encoding="utf-8")


def focused_cases(expected_result: str) -> dict[str, dict[str, str]]:
    out = {}
    for suite, names in check_reports.EXPECTED_CASES.items():
        cases = {name: check_reports.PASS for name in names}
        if expected_result == "RED":
            for name in names:
                if f"{suite}#{name}" in RED_FAILURES:
                    cases[name] = check_reports.FAILURE
        out[suite] = cases
    return out


def filler(count: int) -> dict[str, str]:
    return {f"existingTest{i:03d}": check_reports.PASS for i in range(count)}


def build(tmp: Path, expected_result: str, *, regression_extra: int = 689) -> tuple[Path, Path]:
    focused = tmp / "evidence" / "layout"
    regression = tmp / "evidence" / "regression"
    for suite, cases in focused_cases(expected_result).items():
        module = "designsystem" if suite == DS else "ui"
        write_suite(focused / f"junit-{module}", f"TEST-{suite}.xml", suite, cases)
    for suite, cases in focused_cases(expected_result).items():
        module = "designsystem" if suite == DS else "ui"
        write_suite(regression / f"junit-{module}", f"TEST-{suite}.xml", suite, cases)
    write_suite(regression / "junit-other", "TEST-Existing.xml", "dev.example.ExistingTest",
                filler(regression_extra))
    return focused, regression


class GateHarness(unittest.TestCase):
    def run_gate(self, expected_result: str, focused: Path, regression: Path,
                 focused_exit: str = "0", regression_exit: str = "0") -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = check_reports.main([
                "--expected-result", expected_result,
                "--focused-exit", focused_exit,
                "--regression-exit", regression_exit,
                "--focused-root", str(focused),
                "--regression-root", str(regression),
            ])
        return code, buffer.getvalue()

    def test_green_clean_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            focused, regression = build(Path(tmp), "GREEN")
            code, out = self.run_gate("GREEN", focused, regression)
            self.assertEqual(code, 0, out)
            self.assertIn("verdict: PASS", out)

    def test_red_exact_expected_failures_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            focused, regression = build(Path(tmp), "RED")
            code, out = self.run_gate("RED", focused, regression, "1", "1")
            self.assertEqual(code, 0, out)

    def test_unexpected_failure_in_green_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            focused, regression = build(Path(tmp), "GREEN")
            cases = dict(focused_cases("GREEN")[DS])
            cases["shortHebrewParagraphStartsAtTheRightContentEdge"] = check_reports.FAILURE
            write_suite(focused / "junit-designsystem", f"TEST-{DS}.xml", DS, cases)
            code, out = self.run_gate("GREEN", focused, regression)
            self.assertEqual(code, 1)
            self.assertIn("::error::", out)

    def test_unexpected_existing_suite_failure_in_green_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            focused, regression = build(Path(tmp), "GREEN")
            cases = filler(689)
            cases["existingTest000"] = check_reports.FAILURE
            write_suite(regression / "junit-other", "TEST-Existing.xml", "dev.example.ExistingTest", cases)
            code, out = self.run_gate("GREEN", focused, regression)
            self.assertEqual(code, 1)

    def test_missing_reports_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            focused, regression = build(Path(tmp), "GREEN")
            code, out = self.run_gate("GREEN", Path(tmp) / "nope", regression)
            self.assertEqual(code, 1)
            self.assertIn("report directory is missing", out)

    def test_empty_report_directory_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            focused, regression = build(Path(tmp), "GREEN")
            empty = Path(tmp) / "empty"
            empty.mkdir()
            code, out = self.run_gate("GREEN", focused, empty)
            self.assertEqual(code, 1)
            self.assertIn("no JUnit XML reports", out)

    def test_unparsable_report_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            focused, regression = build(Path(tmp), "GREEN")
            (focused / "junit-ui" / "TEST-Broken.xml").write_text("<testsuite><testcase", encoding="utf-8")
            code, out = self.run_gate("GREEN", focused, regression)
            self.assertEqual(code, 1)
            self.assertIn("unparsable JUnit report", out)

    def test_errored_case_fails_even_in_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            focused, regression = build(Path(tmp), "RED")
            cases = dict(focused_cases("RED")[UI])
            cases["theDraftKeepsItsExactBytes"] = check_reports.ERROR
            write_suite(focused / "junit-ui", f"TEST-{UI}.xml", UI, cases)
            code, out = self.run_gate("RED", focused, regression, "1", "1")
            self.assertEqual(code, 1)
            self.assertIn("errored", out)

    def test_skipped_control_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            focused, regression = build(Path(tmp), "GREEN")
            cases = dict(focused_cases("GREEN")[UI])
            cases["englishDraftStartsAtTheLeftContentEdge"] = check_reports.SKIP
            write_suite(focused / "junit-ui", f"TEST-{UI}.xml", UI, cases)
            code, out = self.run_gate("GREEN", focused, regression)
            self.assertEqual(code, 1)
            self.assertIn("skipped", out)

    def test_missing_focused_case_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            focused, regression = build(Path(tmp), "GREEN")
            cases = dict(focused_cases("GREEN")[DS])
            del cases["linkedHebrewParagraphStartsAtTheRightContentEdge"]
            write_suite(focused / "junit-designsystem", f"TEST-{DS}.xml", DS, cases)
            code, out = self.run_gate("GREEN", focused, regression)
            self.assertEqual(code, 1)
            self.assertIn("missing expected case", out)

    def test_extra_focused_case_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            focused, regression = build(Path(tmp), "GREEN")
            cases = dict(focused_cases("GREEN")[UI])
            cases["someNewCase"] = check_reports.PASS
            write_suite(focused / "junit-ui", f"TEST-{UI}.xml", UI, cases)
            code, out = self.run_gate("GREEN", focused, regression)
            self.assertEqual(code, 1)
            self.assertIn("unexpected case", out)

    def test_regression_below_case_floor_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            focused, regression = build(Path(tmp), "GREEN", regression_extra=680)
            code, out = self.run_gate("GREEN", focused, regression)
            self.assertEqual(code, 1)
            self.assertIn("below the expected floor", out)

    def test_green_with_failing_gradle_exit_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            focused, regression = build(Path(tmp), "GREEN")
            code, out = self.run_gate("GREEN", focused, regression, focused_exit="1")
            self.assertEqual(code, 1)
            self.assertIn("GREEN requires 0", out)

    def test_missing_gradle_exit_status_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            focused, regression = build(Path(tmp), "GREEN")
            code, out = self.run_gate("GREEN", focused, regression, focused_exit="")
            self.assertEqual(code, 1)
            self.assertIn("recorded no Gradle exit status", out)

    def test_red_with_successful_gradle_exit_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            focused, regression = build(Path(tmp), "RED")
            code, out = self.run_gate("RED", focused, regression, focused_exit="0", regression_exit="1")
            self.assertEqual(code, 1)
            self.assertIn("RED requires the pre-fix tests to fail", out)

    def test_red_missing_an_expected_failure_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            focused, regression = build(Path(tmp), "RED")
            cases = dict(focused_cases("RED")[UI])
            cases["hebrewParagraphThenNewlineEnglishStartsAtTheLeftContentEdge"] = check_reports.PASS
            write_suite(focused / "junit-ui", f"TEST-{UI}.xml", UI, cases)
            code, out = self.run_gate("RED", focused, regression, "1", "1")
            self.assertEqual(code, 1)
            self.assertIn("did not reproduce the expected geometry failure", out)

    def test_red_with_unexpected_control_failure_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            focused, regression = build(Path(tmp), "RED")
            cases = dict(focused_cases("RED")[DS])
            cases["englishParagraphStartsAtTheLeftContentEdge"] = check_reports.FAILURE
            write_suite(focused / "junit-designsystem", f"TEST-{DS}.xml", DS, cases)
            code, out = self.run_gate("RED", focused, regression, "1", "1")
            self.assertEqual(code, 1)
            self.assertIn("unexpected failing case", out)

    def test_red_regression_extra_failure_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            focused, regression = build(Path(tmp), "RED")
            cases = filler(689)
            cases["existingTest001"] = check_reports.FAILURE
            write_suite(regression / "junit-other", "TEST-Existing.xml", "dev.example.ExistingTest", cases)
            code, out = self.run_gate("RED", focused, regression, "1", "1")
            self.assertEqual(code, 1)
            self.assertIn("regression run has failing case", out)

    def test_red_without_reports_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            focused, regression = build(Path(tmp), "RED")
            code, out = self.run_gate("RED", Path(tmp) / "gone", regression, "1", "1")
            self.assertEqual(code, 1)

    def test_unknown_expected_result_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            focused, regression = build(Path(tmp), "GREEN")
            code, out = self.run_gate("MAYBE", focused, regression)
            self.assertEqual(code, 1)

    def test_duplicate_case_identity_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            focused, regression = build(Path(tmp), "GREEN")
            duplicate = focused / "junit-ui" / "TEST-Duplicate.xml"
            duplicate.write_text(
                f'<testsuite name="{UI}">'
                f'<testcase classname="{UI}" name="theDraftKeepsItsExactBytes"/>'
                "</testsuite>",
                encoding="utf-8",
            )
            code, out = self.run_gate("GREEN", focused, regression)
            self.assertEqual(code, 1)
            self.assertIn("duplicate testcase identity", out)


if __name__ == "__main__":
    unittest.main()
