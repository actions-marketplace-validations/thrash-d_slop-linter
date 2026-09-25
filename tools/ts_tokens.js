// Print a file's code tokens as JSON, with comments removed, for comment_guard.py.
// Usage: node ts_tokens.js <path-to-typescript-module> <file>
//
// Tokens come from the TypeScript parser, so JSX, template strings, and regex
// literals are handled correctly. A JSX expression that holds only a comment,
// `{/* ... */}`, is skipped, so deleting one isn't reported as a code change.
// JSDoc blocks are skipped too.
// JSX text is compared with whitespace collapsed.
const ts = require(process.argv[2]);
const fs = require("fs");

const file = process.argv[3];
const text = fs.readFileSync(file, "utf8").replace(/^﻿/, "").replace(/\r\n/g, "\n");
// Baselines are saved as <name>.tsx.orig, so pick the parser from the real extension.
const lower = file.toLowerCase().replace(/\.orig$/, "");
const kind = lower.endsWith(".tsx") ? ts.ScriptKind.TSX
  : lower.endsWith(".jsx") ? ts.ScriptKind.JSX
  : /\.(ts|mts|cts)$/.test(lower) ? ts.ScriptKind.TS
  : ts.ScriptKind.JS;
const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, kind);

const tokens = [];
const isJSDocKind = (k) => k >= ts.SyntaxKind.FirstJSDocNode && k <= ts.SyntaxKind.LastJSDocNode;
function visit(node) {
  // The parser attaches /** */ blocks to declarations as JSDoc nodes; they're comments.
  if (isJSDocKind(node.kind)) return;
  if (ts.isJsxExpression(node) && !node.expression) return;
  if (node.kind === ts.SyntaxKind.JsxText) {
    const t = node.getText(sf).replace(/\s+/g, " ").trim();
    if (t) tokens.push([node.kind, t, sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1]);
    return;
  }
  const kids = node.getChildren(sf);
  if (kids.length === 0) {
    if (node.kind !== ts.SyntaxKind.EndOfFileToken) {
      tokens.push([node.kind, node.getText(sf), sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1]);
    }
    return;
  }
  kids.forEach(visit);
}
visit(sf);
console.log(JSON.stringify({ tokens, parseErrors: (sf.parseDiagnostics || []).length }));
