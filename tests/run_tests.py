"""Check the styles before a commit or release.

    python tests/run_tests.py

1. Every rule fires at least once on tests/slop-sample.md or
   tests/slop-sample.py, so no rule is silently dead.
2. tests/should-pass.md, .py, and .html produce zero alerts at any level,
   so ordinary writing doesn't trip a rule. They're linted twice: with the
   plain config, and with a vocabulary active, the way dev-kit repos run.

3. LinkedIn posts in tests/linkedin, which opt into NoSlopLinkedIn by their
   .linkedin.md name. Each should-flag post meets the warning count in its
   `<!-- min: N ... -->` header, every NoSlopLinkedIn rule fires on at least
   one of them, and should-pass posts get zero warnings.

4. Optional: every .md and .txt file under SLOP_CORPUS (paths separated by
   os.pathsep, files or folders) produces zero alerts at warning level.
   Point it at your own finished writing. CurlyQuotes is skipped there
   because `vale fix` straightens those.

Uses vale from PATH, or the path in the VALE environment variable. Exits 1 if
any check fails.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".vale.ini"
VALE = os.environ.get("VALE", "vale")
DIRTY = {"NoSlop": ROOT / "tests" / "slop-sample.md", "NoSlopCode": ROOT / "tests" / "slop-sample.py"}
CLEAN = [ROOT / "tests" / "should-pass.md", ROOT / "tests" / "should-pass.py", ROOT / "tests" / "should-pass.html"]
LINKEDIN = ROOT / "tests" / "linkedin"
MIN_HEADER = re.compile(r"<!-- min: (\d+)")


def lint(path: Path, config: Path = CONFIG, level: str = "suggestion") -> list[dict]:
    result = subprocess.run(
        [VALE, f"--config={config}", f"--minAlertLevel={level}", "--output=JSON", str(path)],
        capture_output=True, text=True, encoding="utf-8", check=False,
    )
    if result.returncode > 1:
        sys.exit(f"vale failed on {path.name}: {result.stderr.strip()}")
    data = json.loads(result.stdout or "{}")
    return [alert for alerts in data.values() for alert in alerts]


def vocab_config(tmp: Path) -> Path:
    """Write a copy of the config with a vocabulary active.

    A Vocab changes how Vale applies some rules: it merged into HeadingCase's
    exceptions and flagged "Run it" as a miscased IT.
    """
    styles = tmp / "styles"
    shutil.copytree(ROOT / "styles", styles)
    vocab = styles / "config" / "vocabularies" / "Test"
    vocab.mkdir(parents=True)
    (vocab / "accept.txt").write_text("[Rr]ealms?\n", encoding="utf-8")
    text = CONFIG.read_text(encoding="utf-8")
    text = text.replace("StylesPath = styles", f"StylesPath = {styles.as_posix()}\nVocab = Test", 1)
    config = tmp / "vocab.ini"
    config.write_text(text, encoding="utf-8")
    return config


def main() -> int:
    failed = False

    for style, sample in DIRTY.items():
        rules = {f"{style}.{p.stem}" for p in (ROOT / "styles" / style).glob("*.yml")}
        fired = {a["Check"] for a in lint(sample)}
        dead = sorted(rules - fired)
        print(f"{style}: {len(rules) - len(dead)}/{len(rules)} rules fire on {sample.name}")
        for rule in dead:
            print(f"  dead: {rule}")
        failed |= bool(dead)

    with tempfile.TemporaryDirectory() as tmp:
        configs = {"plain": CONFIG, "with vocab": vocab_config(Path(tmp))}
        for label, config in configs.items():
            for clean in CLEAN:
                alerts = lint(clean, config)
                print(f"{clean.name} ({label}): {len(alerts)} alerts")
                for a in alerts:
                    print(f"  line {a['Line']}: {a['Check']}: {a['Message']}")
                failed |= bool(alerts)

    fired = set()
    for post in sorted((LINKEDIN / "should-flag").glob("*.linkedin.md")):
        header = MIN_HEADER.search(post.read_text(encoding="utf-8"))
        if not header:
            print(f"{post.name}: no <!-- min: N --> header")
            failed = True
            continue
        want = int(header.group(1))
        got = len(lint(post, level="warning"))
        fired |= {a["Check"] for a in lint(post)}
        print(f"{post.name}: {got} warnings, needs {want}")
        failed |= got < want
    rules = {f"NoSlopLinkedIn.{p.stem}" for p in (ROOT / "styles" / "NoSlopLinkedIn").glob("*.yml")}
    dead = sorted(rules - fired)
    print(f"NoSlopLinkedIn: {len(rules) - len(dead)}/{len(rules)} rules fire on tests/linkedin/should-flag")
    for rule in dead:
        print(f"  dead: {rule}")
    failed |= bool(dead)
    for post in sorted((LINKEDIN / "should-pass").glob("*.linkedin.md")):
        alerts = lint(post, level="warning")
        print(f"{post.name}: {len(alerts)} warnings")
        for a in alerts:
            print(f"  line {a['Line']}: {a['Check']}: {a['Message']}")
        failed |= bool(alerts)

    for entry in filter(None, os.environ.get("SLOP_CORPUS", "").split(os.pathsep)):
        base = Path(entry)
        files = [base] if base.is_file() else sorted(
            p for p in base.rglob("*") if p.suffix in (".md", ".txt")
        )
        if not files:
            print(f"corpus: nothing to lint at {base}")
            failed = True
        for path in files:
            alerts = [a for a in lint(path, level="warning") if a["Check"] != "NoSlop.CurlyQuotes"]
            print(f"corpus {path.name}: {len(alerts)} alerts")
            for a in alerts:
                print(f"  line {a['Line']}: {a['Check']}: {a['Message']}")
            failed |= bool(alerts)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
