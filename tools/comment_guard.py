"""Prove a comment-only edit didn't touch code.

Usage: python comment_guard.py [--protect START END ...] ORIGINAL EDITED

Checks, in order:
  1. Line endings and BOM are unchanged (a PS 5.1 script can break on either).
  2. Protected text is byte-identical: every block from a START marker to its
     END marker given with --protect (for example, a YAML manifest that a
     program parses out of a comment), and directive lines (#Requires, #region,
     noqa, type: ignore, pragma, pylint, fmt, isort, mypy, shebang, coding).
  3. The code is identical once comments are removed.
     - .ps1/.psm1: comment-stripped lines must match line for line.
     - .py: the token stream minus comments and docstrings must match, token and
       column. Docstrings may change except user-facing ones, which are locked:
       FastAPI route handlers (render in /docs), Pydantic models (render as
       schema descriptions), and the module docstring when the file reads
       __doc__. The edited file must still compile.

     - .ts/.tsx/.js/.jsx/.mjs/.cjs: the TypeScript parser's token stream minus
       comments must match (tools/ts_tokens.js; needs node and a typescript
       package, found via $SLOP_TS_MODULE or the nearest node_modules). A JSX
       `{/* comment */}` container may be deleted. No new parse errors allowed.

Exits 0 when the edit is comment-only, 1 with a reason when it isn't.
Other languages fail closed until a checker is added.
"""
import argparse
import ast
import io
import re
import sys
import tokenize
from pathlib import Path

DIRECTIVE = re.compile(
    r"^\s*(#!|#requires\s+-|#\s*(end)?region\b|.*#\s*noqa\b|.*#\s*type:\s*ignore"
    r"|.*#\s*pragma\b|.*#\s*pylint:|.*#\s*fmt:|.*#\s*isort:|.*#\s*mypy:|.*-\*-\s*coding"
    r"|.*(//|/\*)\s*(eslint-|@ts-|prettier-ignore|istanbul ignore|jshint|global\s)"
    r"|\s*///\s*<reference)",
    re.IGNORECASE,
)
TS_EXTS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts"}
ROUTE_METHODS = {"get", "post", "put", "delete", "patch", "options", "head",
                 "api_route", "websocket", "route"}
MODEL_BASES = {"BaseModel", "BaseSettings", "RootModel"}


def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


def ps1_code(text):
    """Return the code lines of a PowerShell script with comments removed."""
    out, in_block, here_end = [], False, None
    for line in text.split("\n"):
        line = line.rstrip("\r")
        if here_end:
            out.append(line)
            if line.startswith(here_end):
                here_end = None
            continue
        if in_block:
            if "#>" in line:
                in_block = False
                line = line.split("#>", 1)[1]
            else:
                continue
        code, i, quote = [], 0, None
        while i < len(line):
            c = line[i]
            if quote:
                code.append(c)
                if c == "`" and quote == '"' and i + 1 < len(line):
                    code.append(line[i + 1])
                    i += 1
                elif c == quote:
                    quote = None
            elif c in "'\"":
                quote = c
                code.append(c)
            elif line.startswith("<#", i):
                rest = line[i + 2:]
                if "#>" in rest:
                    line = line[:i] + rest.split("#>", 1)[1]
                    continue
                in_block = True
                break
            # PowerShell starts a comment only where a token can start: `a#b`
            # and `https://x/#frag` are single tokens, not code plus a comment.
            elif c == "#" and (i == 0 or line[i - 1] in " \t;(){}|,=&"):
                break
            else:
                code.append(c)
            i += 1
        stripped = "".join(code).rstrip()
        if stripped.endswith('@"') or stripped.endswith("@'"):
            here_end = stripped[-1] + "@"
        if stripped.strip():
            out.append(stripped)
    return out


def ps1_check(orig, new):
    oc, nc = ps1_code(orig), ps1_code(new)
    for n, (a, b) in enumerate(zip(oc, nc), 1):
        if a != b:
            fail(f"code line {n} differs:\n  was: {a.strip()}\n  now: {b.strip()}")
    if len(oc) != len(nc):
        fail(f"code line count changed: {len(oc)} -> {len(nc)}")
    return f"{len(oc)} code lines identical"


def _docstrings(tree):
    """Map each module/class/function node to its docstring Constant."""
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                found[node] = body[0].value
    return found


def _base_name(b):
    if isinstance(b, ast.Name):
        return b.id
    if isinstance(b, ast.Attribute):
        return b.attr
    if isinstance(b, ast.Subscript):
        return _base_name(b.value)
    return ""


def _locked(tree):
    """Docstrings that users see, keyed by owner."""
    uses_doc = any(isinstance(n, ast.Name) and n.id == "__doc__" for n in ast.walk(tree))
    locked = {}
    for node, const in _docstrings(tree).items():
        key = None
        if isinstance(node, ast.Module) and uses_doc:
            key = "module docstring (file reads __doc__)"
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in node.decorator_list:
                f = d.func if isinstance(d, ast.Call) else d
                if isinstance(f, ast.Attribute) and f.attr in ROUTE_METHODS:
                    key = f"route handler {node.name}()"
        elif isinstance(node, ast.ClassDef):
            if any(_base_name(b) in MODEL_BASES for b in node.bases):
                key = f"Pydantic model {node.name}"
        if key:
            locked[key] = const.value
    return locked


def _code_tokens(text, tree):
    """Tokens minus comments, blank-line NLs, and docstrings, with columns."""
    doc_starts = {(c.lineno, c.col_offset) for c in _docstrings(tree).values()}
    out, skip_newline = [], False
    for t in tokenize.generate_tokens(io.StringIO(text).readline):
        if t.type in (tokenize.COMMENT, tokenize.NL, tokenize.ENCODING):
            continue
        if t.type == tokenize.STRING and t.start in doc_starts:
            skip_newline = True
            continue
        if skip_newline and t.type == tokenize.NEWLINE:
            skip_newline = False
            continue
        skip_newline = False
        # A NEWLINE token sits after any inline comment, so its column moves
        # when the comment changes. Only its presence matters.
        col = None if t.type in (tokenize.NEWLINE, tokenize.ENDMARKER) else t.start[1]
        out.append((tokenize.tok_name[t.type], t.string, col, t.start[0]))
    return out


def py_check(orig, new, name):
    try:
        compile(new, name, "exec")
    except SyntaxError as e:
        fail(f"edited file no longer compiles: {e}")
    otree, ntree = ast.parse(orig), ast.parse(new)
    ol, nl = _locked(otree), _locked(ntree)
    for key in ol:
        if ol[key] != nl.get(key):
            fail(f"locked docstring changed: {key}")
    ot, nt = _code_tokens(orig, otree), _code_tokens(new, ntree)
    for a, b in zip(ot, nt):
        if a[:3] != b[:3]:
            fail(f"code differs near original line {a[3]} / edited line {b[3]}:\n"
                 f"  was: {a[1]!r} at col {a[2]}\n  now: {b[1]!r} at col {b[2]}")
    if len(ot) != len(nt):
        fail(f"code token count changed: {len(ot)} -> {len(nt)}")
    return (f"{len(ot)} code tokens identical, {len(ol)} locked docstrings untouched, "
            f"compiles")


def _find_ts_module(start):
    """Locate a typescript package: $SLOP_TS_MODULE, else the nearest node_modules."""
    import os
    env = os.environ.get("SLOP_TS_MODULE")
    if env:
        return env
    p = Path(start).resolve().parent
    for d in [p, *p.parents]:
        for cand in (d / "node_modules" / "typescript", d / "frontend" / "node_modules" / "typescript"):
            if (cand / "package.json").exists():
                return str(cand)
    return None


def ts_check(orig_path, new_path):
    import json
    import subprocess
    mod = _find_ts_module(new_path)
    if not mod:
        fail("no typescript package found; set SLOP_TS_MODULE to a node_modules/typescript dir")
    script = Path(__file__).with_name("ts_tokens.js")
    runs = []
    for p in (orig_path, new_path):
        r = subprocess.run(["node", str(script), mod, str(p)], capture_output=True, text=True)
        if r.returncode != 0:
            fail(f"token dump failed for {p}: {r.stderr.strip()[:300]}")
        runs.append(json.loads(r.stdout))
    (o, n) = runs
    if n["parseErrors"] > o["parseErrors"]:
        fail(f"edited file has new parse errors ({o['parseErrors']} -> {n['parseErrors']})")
    for a, b in zip(o["tokens"], n["tokens"]):
        if a[:2] != b[:2]:
            fail(f"code differs near original line {a[2]} / edited line {b[2]}:\n"
                 f"  was: {a[1][:80]!r}\n  now: {b[1][:80]!r}")
    if len(o["tokens"]) != len(n["tokens"]):
        fail(f"code token count changed: {len(o['tokens'])} -> {len(n['tokens'])}")
    return f"{len(o['tokens'])} code tokens identical (TypeScript parser)"


CHECKERS = {".ps1": ps1_check, ".psm1": ps1_check, ".py": py_check}
CHECKERS.update({e: ts_check for e in TS_EXTS})


def main(orig_path, new_path, protect=()):
    orig_b, new_b = Path(orig_path).read_bytes(), Path(new_path).read_bytes()
    for label, b in (("original", orig_b), ("edited", new_b)):
        if b"\r\n" in b and re.search(rb"(?<!\r)\n", b):
            fail(f"{label} file has mixed line endings")
    if (b"\r\n" in orig_b) != (b"\r\n" in new_b):
        fail("line ending style changed")
    if orig_b.startswith(b"\xef\xbb\xbf") != new_b.startswith(b"\xef\xbb\xbf"):
        fail("BOM added or removed")

    orig, new = orig_b.decode("utf-8-sig"), new_b.decode("utf-8-sig")
    for start, end in protect:
        block = re.compile(re.escape(start) + r"[\s\S]*?" + re.escape(end))
        if block.findall(orig) != block.findall(new):
            fail(f"protected block {start} ... {end} changed")

    od = [l for l in orig.splitlines() if DIRECTIVE.match(l)]
    nd = [l for l in new.splitlines() if DIRECTIVE.match(l)]
    if od != nd:
        fail(f"directive lines changed: {set(od) ^ set(nd)}")

    ext = Path(new_path).suffix.lower()
    check = CHECKERS.get(ext)
    if check is None:
        fail(f"no checker for {ext}")
    if check is py_check:
        detail = py_check(orig.replace("\r\n", "\n"), new.replace("\r\n", "\n"), new_path)
    elif check is ts_check:
        detail = ts_check(orig_path, new_path)
    else:
        detail = check(orig, new)
    print(f"PASS: comment-only edit. {detail}; {len(protect)} protected block types and {len(od)} directive lines untouched.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Prove a comment-only edit didn't touch code.")
    ap.add_argument("original")
    ap.add_argument("edited")
    ap.add_argument("--protect", nargs=2, action="append", default=[], metavar=("START", "END"),
                    help="Marker pair whose enclosed text must stay byte-identical. Repeatable.")
    args = ap.parse_args()
    main(args.original, args.edited, [tuple(p) for p in args.protect])
