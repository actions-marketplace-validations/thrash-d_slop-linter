"""Turns Vale's JSON output into GitHub Actions annotations and decides the exit code.

Usage: vale --output=JSON ... | python annotate.py <fail-on>
fail-on is error, warning, or none.
"""

import json
import sys

LEVELS = {"suggestion": 0, "warning": 1, "error": 2}
COMMANDS = {"suggestion": "notice", "warning": "warning", "error": "error"}


def escape(text):
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main(raw, fail_on):
    threshold = {"error": 2, "warning": 1, "none": 3}[fail_on]
    worst = -1
    count = 0
    for path, alerts in sorted(json.loads(raw or "{}").items()):
        for a in alerts:
            sev = a["Severity"]
            worst = max(worst, LEVELS[sev])
            count += 1
            print(f"::{COMMANDS[sev]} file={path},line={a['Line']},col={a['Span'][0]},"
                  f"title={a['Check']}::{escape(a['Message'])}")
    print(f"slop-linter: {count} finding(s).")
    return 1 if worst >= threshold else 0


if __name__ == "__main__":
    sys.exit(main(sys.stdin.buffer.read().decode("utf-8"), sys.argv[1] if len(sys.argv) > 1 else "error"))
