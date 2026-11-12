"""Reject incomplete browser acceptance, including codec-related skips."""

import json
import sys
from pathlib import Path


def complete(report):
    stats = report.get("stats", {})
    return (
        not report.get("errors")
        and stats.get("expected", 0) > 0
        and all(stats.get(key) == 0 for key in ("unexpected", "flaky", "skipped"))
    )


if __name__ == "__main__":
    report = json.loads(Path(sys.argv[1]).read_text())
    if not complete(report):
        raise SystemExit(
            "INCOMPLETE: browser failures/skips or no passing tests; inspect report.json"
        )
    print("PASS: all selected browser tests passed without skips or retries")
