#!/usr/bin/env python3
"""Validate the RTL harness dispatch inputs before any shell uses them.

The workflow hands the raw `production_revision` / `expected_result` inputs to
this script through environment variables only; nothing is interpolated into
shell source. A revision is accepted only as a full 40-character lowercase
commit ID, which is the only form that is safe to quote and unambiguous to
resolve. Short IDs, branch names, ranges and anything containing shell
metacharacters are rejected without being echoed.

Exits non-zero with `::error::` annotations on any invalid combination.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")

GREEN = "GREEN"
RED = "RED"
MODES = (GREEN, RED)


def fail(message: str) -> None:
    print(f"::error::{message}")


def resolve_mode(raw_mode: str, event_name: str) -> str:
    """An absent dispatch input (push builds) means GREEN."""
    mode = (raw_mode or "").strip() or GREEN
    if mode not in MODES:
        raise ValueError(f"expected_result must be one of {MODES}, got an unrecognised value")
    if mode == RED and event_name != "workflow_dispatch":
        raise ValueError("RED mode is only available on a manual workflow_dispatch run")
    return mode


def resolve_revision(mode: str, raw_revision: str) -> str:
    revision = (raw_revision or "").strip()
    if mode == GREEN:
        if revision:
            raise ValueError(
                "production_revision was supplied without expected_result=RED; refusing to substitute "
                "production files into a run that claims to be GREEN"
            )
        return ""
    if not revision:
        raise ValueError("RED mode requires the full 40-character commit ID of the pre-fix revision")
    if not FULL_SHA.match(revision):
        # Never echo the value: it may contain shell syntax or control characters.
        raise ValueError(
            "production_revision must be exactly 40 lowercase hexadecimal characters "
            f"(received {len(revision)} characters)"
        )
    return revision


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-result", default="")
    parser.add_argument("--production-revision", default="")
    parser.add_argument("--event-name", default=os.environ.get("GITHUB_EVENT_NAME", ""))
    parser.add_argument("--github-output", default="", help="path to append key=value outputs to")
    args = parser.parse_args(argv)

    try:
        mode = resolve_mode(args.expected_result, args.event_name)
        revision = resolve_revision(mode, args.production_revision)
    except ValueError as exc:
        fail(str(exc))
        return 1

    print(f"expected_result={mode}")
    print(f"production_revision={revision or '(none: exact HEAD source)'}")

    outputs = {"mode": mode, "production_revision": revision}
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as handle:
            for key, value in outputs.items():
                handle.write(f"{key}={value}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
