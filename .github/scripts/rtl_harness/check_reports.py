#!/usr/bin/env python3
"""Fail-closed verdict for the rendered RTL layout harness.

The harness is expected to pass after the production fix (GREEN) and to fail in
exactly nine named geometry assertions when the pre-fix production files are
restored (RED). Both facts are contractual, so this gate decides on test
*identities*, not on the presence of a JUnit report:

* GREEN requires both Gradle invocations to exit 0, all 17 rendered cases
  present and passing, and the pre-existing host suites present with no
  failures, errors or skips.
* RED requires both Gradle invocations to exit non-zero, exactly the same 17
  cases to be present, exactly the nine expected geometry cases to fail, every
  control to pass, and no other failure, error or skip anywhere.

Missing or unparsable reports, a compilation/setup failure, a zero-test report,
an unexpected failure and an unexpected pass in RED all end the run non-zero.
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DESIGNSYSTEM_SUITE = "dev.hermeskotlin.designsystem.components.MarkdownRtlLayoutTest"
UI_SUITE = "dev.hermeskotlin.ui.chat.ComposerRtlLayoutTest"

# The 17 rendered cases the harness adds, as (suite, method) identities.
EXPECTED_CASES = {
    DESIGNSYSTEM_SUITE: (
        "englishParagraphStartsAtTheLeftContentEdge",
        "fullWidthRtlReferenceTextStartsAtTheRightContentEdge",
        "shortHebrewParagraphStartsAtTheRightContentEdge",
        "secondHebrewParagraphStartsAtTheRightContentEdge",
        "highlightedHebrewParagraphStartsAtTheRightContentEdge",
        "linkedHebrewParagraphStartsAtTheRightContentEdge",
        "wrappedHebrewParagraphKeepsEveryLineAtTheRightEdge",
        "englishParagraphAfterHebrewStaysLeftInTheSameReply",
        "englishParagraphStaysLeftInAnRtlAmbientContext",
    ),
    UI_SUITE: (
        "englishDraftStartsAtTheLeftContentEdge",
        "fullWidthRtlReferenceTextStartsAtTheRightContentEdge",
        "oneHebrewLetterIsAnchoredAtTheRightContentEdge",
        "twoHebrewLettersAreAnchoredAtTheRightContentEdge",
        "shortHebrewDraftIsAnchoredAtTheRightContentEdge",
        "englishDraftStaysLeftInAnRtlAmbientContext",
        "wrappedHebrewLinesShareTheRightContentEdge",
        "theDraftKeepsItsExactBytes",
    ),
}

# Pre-fix production code must fail these and nothing else. Every other rendered
# case is a control and has to keep passing.
EXPECTED_FAILURES_WHEN_RED = {
    DESIGNSYSTEM_SUITE: (
        "shortHebrewParagraphStartsAtTheRightContentEdge",
        "secondHebrewParagraphStartsAtTheRightContentEdge",
        "highlightedHebrewParagraphStartsAtTheRightContentEdge",
        "linkedHebrewParagraphStartsAtTheRightContentEdge",
        "englishParagraphStaysLeftInAnRtlAmbientContext",
    ),
    UI_SUITE: (
        "oneHebrewLetterIsAnchoredAtTheRightContentEdge",
        "twoHebrewLettersAreAnchoredAtTheRightContentEdge",
        "shortHebrewDraftIsAnchoredAtTheRightContentEdge",
        "englishDraftStaysLeftInAnRtlAmbientContext",
    ),
}

# The pre-existing designsystem + ui host suites independently reviewed as 706
# unique cases. A regression run below that floor is a broken collection, not a
# passing suite.
MIN_REGRESSION_CASES = 706

PASS, FAILURE, ERROR, SKIP = "passed", "failure", "error", "skipped"


class ReportError(RuntimeError):
    pass


def parse_reports(root: Path) -> dict[tuple[str, str], str]:
    """Return {(classname, testname): status} for every JUnit XML under root."""
    if not root.is_dir():
        raise ReportError(f"report directory is missing: {root}")
    xml_files = sorted(root.rglob("*.xml"))
    if not xml_files:
        raise ReportError(f"no JUnit XML reports under {root}")

    cases: dict[tuple[str, str], str] = {}
    for path in xml_files:
        try:
            tree = ET.parse(path)
        except ET.ParseError as exc:
            raise ReportError(f"unparsable JUnit report {path}: {exc}") from exc
        for element in tree.getroot().iter("testcase"):
            classname = (element.get("classname") or "").strip()
            name = (element.get("name") or "").strip()
            if not classname or not name:
                raise ReportError(f"testcase without classname/name in {path}")
            if name.startswith(f"{classname}."):
                name = name[len(classname) + 1 :]
            key = (classname, name)
            if key in cases:
                raise ReportError(f"duplicate testcase identity {classname}#{name} in {path}")
            if element.find("failure") is not None:
                status = FAILURE
            elif element.find("error") is not None:
                status = ERROR
            elif element.find("skipped") is not None:
                status = SKIP
            else:
                status = PASS
            cases[key] = status
    if not cases:
        raise ReportError(f"JUnit reports under {root} contain no test cases")
    return cases


def suite_cases(cases: dict[tuple[str, str], str], suite: str) -> dict[str, str]:
    return {name: status for (classname, name), status in cases.items() if classname == suite}


def statuses(cases: dict[tuple[str, str], str], wanted: str) -> list[str]:
    return sorted(f"{suite}#{name}" for (suite, name), status in cases.items() if status == wanted)


def expected_suite_matrix() -> dict[str, set[str]]:
    return {suite: set(names) for suite, names in EXPECTED_CASES.items()}


def check_focused(
    cases: dict[tuple[str, str], str], expected_result: str, problems: list[str]
) -> None:
    matrix = expected_suite_matrix()
    for suite, names in matrix.items():
        actual = suite_cases(cases, suite)
        missing = sorted(names - set(actual))
        extra = sorted(set(actual) - names)
        if missing:
            problems.append(f"focused run is missing expected case(s) in {suite}: {', '.join(missing)}")
        if extra:
            problems.append(f"focused run reported unexpected case(s) in {suite}: {', '.join(extra)}")
        for name, status in sorted(actual.items()):
            if status == ERROR:
                problems.append(f"focused case {suite}#{name} errored (infrastructure/setup failure, not a geometry assertion)")
            elif status == SKIP:
                problems.append(f"focused case {suite}#{name} was skipped")

    other = sorted({suite for (suite, _name) in cases if suite not in matrix})
    if other:
        problems.append(f"focused run reported cases from unexpected suite(s): {', '.join(other)}")

    failures = set(statuses(cases, FAILURE))
    if expected_result == "GREEN":
        if failures:
            problems.append("GREEN run has failing focused case(s): " + ", ".join(sorted(failures)))
        return

    expected_failures = {
        f"{suite}#{name}" for suite, names in EXPECTED_FAILURES_WHEN_RED.items() for name in names
    }
    missing_failures = sorted(expected_failures - failures)
    unexpected_failures = sorted(failures - expected_failures)
    if missing_failures:
        problems.append(
            "RED run did not reproduce the expected geometry failure(s): " + ", ".join(missing_failures)
        )
    if unexpected_failures:
        problems.append("RED run has unexpected failing case(s): " + ", ".join(unexpected_failures))


def check_regression(
    cases: dict[tuple[str, str], str], expected_result: str, problems: list[str]
) -> None:
    total = len(cases)
    if total < MIN_REGRESSION_CASES:
        problems.append(
            f"regression run collected {total} test cases, below the expected floor of {MIN_REGRESSION_CASES}"
        )
    errors = statuses(cases, ERROR)
    skips = statuses(cases, SKIP)
    if errors:
        problems.append("regression run has errored case(s): " + ", ".join(errors[:10]))
    if skips:
        problems.append("regression run has skipped case(s): " + ", ".join(skips[:10]))

    failures = set(statuses(cases, FAILURE))
    expected_failures = {
        f"{suite}#{name}" for suite, names in EXPECTED_FAILURES_WHEN_RED.items() for name in names
    } if expected_result == "RED" else set()

    missing = sorted(expected_failures - failures)
    unexpected = sorted(failures - expected_failures)
    if missing:
        problems.append("regression run did not reproduce the expected failure(s): " + ", ".join(missing))
    if unexpected:
        problems.append("regression run has failing case(s): " + ", ".join(unexpected[:10]))


def parse_exit(raw: str, label: str, problems: list[str]) -> int | None:
    text = (raw or "").strip()
    if not text:
        problems.append(f"{label} recorded no Gradle exit status (the step did not run or was cancelled)")
        return None
    try:
        return int(text)
    except ValueError:
        problems.append(f"{label} recorded an unparsable Gradle exit status")
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-result", required=True)
    parser.add_argument("--focused-exit", default="")
    parser.add_argument("--regression-exit", default="")
    parser.add_argument("--focused-root", required=True)
    parser.add_argument("--regression-root", required=True)
    parser.add_argument("--github-summary", default="")
    args = parser.parse_args(argv)

    expected_result = (args.expected_result or "").strip().upper()
    problems: list[str] = []
    if expected_result not in ("GREEN", "RED"):
        problems.append(f"unknown expected result {args.expected_result!r}")

    focused_exit = parse_exit(args.focused_exit, "focused geometry step", problems)
    regression_exit = parse_exit(args.regression_exit, "existing host suites step", problems)

    if focused_exit is not None:
        if expected_result == "GREEN" and focused_exit != 0:
            problems.append(f"focused geometry tests exited {focused_exit}; GREEN requires 0")
        if expected_result == "RED" and focused_exit == 0:
            problems.append("focused geometry tests exited 0; RED requires the pre-fix tests to fail")
    if regression_exit is not None:
        if expected_result == "GREEN" and regression_exit != 0:
            problems.append(f"existing host suites exited {regression_exit}; GREEN requires 0")
        if expected_result == "RED" and regression_exit == 0:
            problems.append("existing host suites exited 0; the nine geometry cases run there too and must fail")

    focused_cases: dict[tuple[str, str], str] = {}
    regression_cases: dict[tuple[str, str], str] = {}
    try:
        focused_cases = parse_reports(Path(args.focused_root))
    except ReportError as exc:
        problems.append(str(exc))
    try:
        regression_cases = parse_reports(Path(args.regression_root))
    except ReportError as exc:
        problems.append(str(exc))

    if focused_cases:
        check_focused(focused_cases, expected_result, problems)
    if regression_cases:
        check_regression(regression_cases, expected_result, problems)

    print(f"expected_result={expected_result}")
    print(f"focused cases={len(focused_cases)} failures={len(statuses(focused_cases, FAILURE))} "
          f"errors={len(statuses(focused_cases, ERROR))} skipped={len(statuses(focused_cases, SKIP))}")
    print(f"regression cases={len(regression_cases)} failures={len(statuses(regression_cases, FAILURE))} "
          f"errors={len(statuses(regression_cases, ERROR))} skipped={len(statuses(regression_cases, SKIP))}")
    for case in statuses(focused_cases, FAILURE):
        print(f"  focused FAILED {case}")

    summary = None
    if args.github_summary:
        summary = open(args.github_summary, "a", encoding="utf-8")
        summary.write("\n#### Fail-closed verdict\n\n")
        summary.write(f"- expected result: `{expected_result}`\n")
        summary.write(f"- focused cases: {len(focused_cases)} "
                      f"(failures {len(statuses(focused_cases, FAILURE))})\n")
        summary.write(f"- regression cases: {len(regression_cases)} "
                      f"(failures {len(statuses(regression_cases, FAILURE))})\n")
        summary.write(f"- verdict: {'FAIL' if problems else 'PASS'}\n\n")

    if problems:
        for problem in problems:
            print(f"::error::{problem}")
            if summary:
                summary.write(f"- error: {problem}\n")
        if summary:
            summary.close()
        return 1

    print(f"verdict: PASS ({expected_result} as expected)")
    if summary:
        summary.write("- no discrepancies\n")
        summary.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
