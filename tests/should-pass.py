"""Parse backup job logs and summarize failures by cause."""

import re
from collections import Counter
from pathlib import Path

# Log lines look like "2026-09-01T02:00:13Z ERROR AccessDenied: ...".
LINE = re.compile(r"^(\S+) (INFO|WARN|ERROR) (\w+)")

# The old file server truncates paths at 260 characters, so a path of exactly
# that length is almost always cut off, not real.
MAX_PATH = 260


def read_errors(log_dir: Path) -> Counter:
    """Count ERROR lines in every log under log_dir, keyed by error code."""
    counts: Counter = Counter()
    for log in sorted(log_dir.glob("*.log")):
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            m = LINE.match(line)
            if m and m.group(2) == "ERROR":
                counts[m.group(3)] += 1
    return counts


def truncated_paths(lines: list[str]) -> list[str]:
    """Return paths that hit the old server's length limit."""
    return [p for p in lines if len(p) == MAX_PATH]


# Retries stop at two. A third failure means the cause isn't transient, and
# more attempts fill the bucket with partial copies.
MAX_RETRIES = 2
