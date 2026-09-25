"""Build the Vale package zips for a GitHub release.

    python tools/build_release.py

Writes dist/NoSlop.zip and dist/NoSlopCode.zip. Each zip holds one style
folder with the same name, which is the layout `vale sync` expects. Attach
both files to a GitHub release.
"""

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def main() -> None:
    DIST.mkdir(exist_ok=True)
    for style in ("NoSlop", "NoSlopCode"):
        src = ROOT / "styles" / style
        out = DIST / f"{style}.zip"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for rule in sorted(src.glob("*.yml")):
                z.write(rule, f"{style}/{rule.name}")
        print(f"{out.relative_to(ROOT)}: {len(list(src.glob('*.yml')))} rules")


if __name__ == "__main__":
    main()
