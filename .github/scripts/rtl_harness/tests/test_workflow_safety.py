#!/usr/bin/env python3
"""Static safety checks on `.github/workflows/rtl-layout-harness.yml`.

W1 (review finding): dispatch input must never be interpolated into shell
source. GitHub expression substitution happens before the shell parses, so
`${{ inputs.x }}` inside `run:` is script text, not data. This test enforces
that no expression of any kind appears inside a run block, and that the
validated-value path and the fail-closed verdict step are present.

W2: the evidence upload and the summary must be `always()`, and the verdict
step must be the last step so a failed run cannot finish green.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[3] / "workflows" / "rtl-layout-harness.yml"

RUN_KEY = re.compile(r"^(?P<indent>\s*)(?:-\s+)?run:\s*(?P<rest>.*)$")
BLOCK_MARKERS = {"|", ">", "|-", ">-", "|+", ">+"}


def run_blocks(text: str) -> list[tuple[int, str]]:
    """Return [(first_line_number, script_text)] for every `run:` key."""
    lines = text.splitlines()
    blocks: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        match = RUN_KEY.match(lines[index])
        if not match:
            index += 1
            continue
        rest = match.group("rest").strip()
        indent = len(match.group("indent").expandtabs(8))
        if rest and rest not in BLOCK_MARKERS:
            blocks.append((index + 1, rest))
            index += 1
            continue
        script: list[str] = []
        cursor = index + 1
        while cursor < len(lines):
            line = lines[cursor]
            if line.strip() and len(line.expandtabs(8)) - len(line.expandtabs(8).lstrip()) <= indent:
                break
            script.append(line)
            cursor += 1
        blocks.append((index + 1, "\n".join(script)))
        index = cursor
    return blocks


def step_index(text: str, name: str) -> int:
    position = text.find(f"- name: {name}")
    if position < 0:
        raise AssertionError(f"workflow has no step named {name!r}")
    return position


def violations(text: str) -> list[str]:
    problems: list[str] = []

    for line_number, script in run_blocks(text):
        if "${{" in script:
            problems.append(f"run block starting at line {line_number} contains '${{{{' expression text")
        if re.search(r"\$\{\{\s*inputs\.", script):
            problems.append(f"run block starting at line {line_number} interpolates a dispatch input")
        if re.search(r"\$\{\{\s*github\.(event\.)?inputs", script):
            problems.append(f"run block starting at line {line_number} reads event inputs")

    for required in (
        "validate_inputs.py",
        "check_reports.py",
        "--expected-result",
        "persist-credentials: false",
        "expected_result:",
        "production_revision:",
        "Enforce expected outcome",
    ):
        if required not in text:
            problems.append(f"workflow is missing {required!r}")

    if text.count("if: always()") < 3:
        problems.append("summary, upload and verdict steps must all run with if: always()")

    try:
        enforce = step_index(text, "Enforce expected outcome (fail-closed)")
        upload = step_index(text, "Upload geometry, screenshots, JUnit and log")
        summary = step_index(text, "Publish geometry and JUnit results")
    except AssertionError as exc:
        problems.append(str(exc))
        return problems

    if not enforce > upload > summary:
        problems.append("step order must be summary -> upload -> fail-closed verdict")

    tail = text[enforce:]
    if "check_reports.py" not in tail:
        problems.append("the fail-closed verdict step does not invoke check_reports.py")
    if "if: always()" not in tail:
        problems.append("the fail-closed verdict step must run with if: always()")

    if not re.search(r"if: always\(\)\s*\n\s*uses: actions/upload-artifact@", text):
        problems.append("the artifact upload must be if: always()")

    if re.search(r"exit 0\s*$", text.rstrip().splitlines()[-1]):
        problems.append("workflow ends with an unconditional success exit")

    return problems


class WorkflowSafety(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_checked_in_workflow_is_clean(self) -> None:
        problems = violations(self.text)
        self.assertEqual([], problems, "\n".join(problems))

    def test_detects_input_interpolation_in_a_run_block(self) -> None:
        anchor = 'echo "::notice::focused geometry tests exited $status'
        bad = self.text.replace(
            anchor, 'echo "input: ${{ inputs.production_revision }}"', 1
        )
        self.assertNotEqual(bad, self.text, "fixture anchor missing")
        self.assertTrue(any("dispatch input" in p or "expression text" in p for p in violations(bad)))

    def test_detects_missing_verdict_step(self) -> None:
        bad = self.text.replace("Enforce expected outcome (fail-closed)", "Something else")
        self.assertNotEqual(bad, self.text, "fixture anchor missing")
        self.assertTrue(violations(bad))

    def test_detects_unconditional_upload(self) -> None:
        bad = self.text.replace(
            "      - name: Upload geometry, screenshots, JUnit and log\n        if: always()",
            "      - name: Upload geometry, screenshots, JUnit and log",
        )
        self.assertNotEqual(bad, self.text, "fixture anchor missing")
        self.assertTrue(violations(bad))

    def test_detects_inline_run_interpolation(self) -> None:
        anchor = "      - name: Self-test the input validator and the fail-closed gate"
        bad = self.text.replace(
            anchor,
            "      - name: Injected\n        run: echo \"${{ inputs.production_revision }}\"\n" + anchor,
            1,
        )
        self.assertNotEqual(bad, self.text, "fixture anchor missing")
        self.assertTrue(any("dispatch input" in p or "expression text" in p for p in violations(bad)))

    def test_detects_verdict_before_upload(self) -> None:
        enforce_block = self.text[step_index(self.text, "Enforce expected outcome (fail-closed)"):]
        moved = self.text.replace(enforce_block, "")
        moved = moved.replace(
            "      - name: Upload geometry, screenshots, JUnit and log",
            enforce_block.rstrip() + "\n\n      - name: Upload geometry, screenshots, JUnit and log",
            1,
        )
        self.assertNotEqual(moved, self.text, "fixture anchor missing")
        self.assertTrue(any("step order" in p for p in violations(moved)))


if __name__ == "__main__":
    unittest.main()
