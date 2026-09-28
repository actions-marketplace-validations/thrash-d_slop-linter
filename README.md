# slop-linter

Vale rules for the stuff AI writing does and people don't: "delve," em dashes everywhere, "Here's the thing," hedges stacked three deep, and code comments that narrate every line. There are 55 rules, 42 for prose and 13 for code comments.

It also comes with two tools: a Claude Code hook that lints what Claude writes as it writes it, and a guard that proves an AI comment cleanup didn't change the code.

## Why this one

A few Vale packages flag AI tells now, and the word lists overlap a lot. If a word list is all you want, [deslop](https://github.com/JMill/deslop) goes deeper on essay-style tells, and [vale-llm-slop](https://github.com/Syntaf/vale-llm-slop) adds an optional ASD-STE100 style. Try a couple and keep whichever catches your drafts.

This repo covers ground the others don't:

- Code comments get their own style. It flags comments that narrate the code, carry history ("ported from", "replaces the old"), set time-bombs ("for now"), shout in caps, or use future tense. Only comments and docstrings are linted, never strings or code.
- The hook lints as Claude writes. Hits go back to Claude before you see the draft. In a code file, it checks only the text Claude just wrote, so a file full of old comments doesn't block a one-line fix.
- The comment guard proves a cleanup was comment-only. It compares code tokens before and after for Python, PowerShell, and TypeScript, and fails on any change that isn't a comment. That's what makes it safe to hand an AI a few thousand comments.
- The rules were tuned on a real codebase. A cleanup of about 3,900 comments shook out the false positives, and each one got fixed: acronyms and product names in headings (about 450 exceptions), SQL's `NOT` read as shouting, section banners, and aligned tables.

## Example

```text
$ vale --config=.vale.ini example.md

 example.md
 1:4   warning  Use sentence case for 'Getting Started'.                NoSlop.HeadingCase
 3:1   warning  Use 'to' instead of 'In order to'.                      NoSlop.Filler
 3:28  warning  LinkedIn-ism: 'leverage our'.                           NoSlop.LinkedIn
 3:41  warning  Likely AI word 'robust'. Use the plain word or cut it.  NoSlop.AIWordsSoft
 3:74  warning  Em dash. Use a period, comma, or parentheses.           NoSlop.EmDash

✖ 0 errors, 5 warnings and 0 suggestions in 1 file.
```

In a code file, only comments and docstrings get linted:

```text
example.py:2:7:NoSlopCode.Narration:Comment narrates the code ('Here we'). Say why, or delete it.
example.py:2:15:NoSlopCode.Difficulty:'simply' claims difficulty. Cut it.
example.py:2:37:NoSlopCode.FutureTense:Present tense: 'This will return'. Say what it does ('Returns', not 'will return').
```

## Install

You need Vale 3.x. Install it with one of these:

```powershell
winget install -e --id errata-ai.Vale
```

```sh
brew install vale
```

```sh
pip install vale
```

The rules are tested with Vale 3.22.0.

### Styles only

If you only want the rules, install them as Vale packages. Add the `Packages` line to your `.vale.ini`:

```ini
StylesPath = styles
MinAlertLevel = warning
Packages = https://github.com/thrash-d/slop-linter/releases/latest/download/NoSlop.zip, https://github.com/thrash-d/slop-linter/releases/latest/download/NoSlopCode.zip

[*.{md,txt}]
BasedOnStyles = NoSlop

[*.{py,js,ts,tsx,ps1}]
BasedOnStyles = NoSlop, NoSlopCode
```

Then create the styles folder and sync:

```sh
mkdir styles
vale sync
```

Some prose rules, like heading case and contractions, make no sense inside a code comment. This repo's [`.vale.ini`](.vale.ini) turns them off for code files. Copy its code section into yours.

The `latest` URLs pick up new rules as soon as they're released. To control when that happens, replace `latest/download` with `download/TAG` for a specific release.

### Full toolkit

For the hook, the batch runner, the comment guard, and the tests, clone the repo:

```sh
git clone https://github.com/thrash-d/slop-linter.git
```

The styles are read straight from the `styles/` folder, so there's no `vale sync` step.

## Run it from the command line

Point Vale at this repo's config and pass the files to check:

```sh
vale --config=SLOP_LINTER_DIR/.vale.ini draft.md src/
```

Replace `SLOP_LINTER_DIR` with the path to your clone.

To sweep a whole project and rank the hits by rule and by file, use the batch runner:

```powershell
.\run-qa.ps1 -Path C:\src\myproject -Exclude data,dist -Level warning -OutFile hits.tsv
```

In a git repo, the runner lints only files git tracks. Add `-All` to lint every file in the tree, tracked or not. Outside a git repo, it always walks the whole tree.

`-Exclude` adds folder names to skip on top of the defaults (`node_modules`, `.git`, `dist`, `build`, virtual environments, and caches). Content folders like `data/` aren't skipped by default, so exclude generated output yourself. `-OutFile` writes every hit as tab-separated values.

## Run it in GitHub Actions

The repo is also a GitHub Action. It installs Vale, lints the files you name with these rules, and puts each hit on its line in the pull request:

```yaml
- uses: actions/checkout@v5
- uses: thrash-d/slop-linter@v1
  with:
    files: README.md docs/
    fail-on: warning
```

`files` defaults to the whole repo. `fail-on` sets the lowest level that fails the step: `error` (the default), `warning`, or `none` to report without failing. To use your own `.vale.ini`, pass its path as `config`. The action runs on Linux runners.

## Run it as a hook

`hook/vale-hook.ps1` is a Claude Code `PostToolUse` hook. After every Write, Edit, or MultiEdit, it lints what Claude wrote. If anything at warning level or higher is left, it exits with code 2, which sends the hits back to Claude to fix.

- Prose files (`.md` and `.txt`) under a folder named `Writing` are linted whole. The hook straightens curly quotes first.
- In code and HTML files, only the new text is linted: the Edit `new_string`, each MultiEdit edit, or the Write content. Old text elsewhere in the file never blocks an edit. Paths under `node_modules`, `.git`, `dist`, `build`, `vendor`, and virtual environments are skipped.

To install it:

1. Copy the `hooks` block from `hook/settings-snippet.json` into your Claude Code settings. Use `~/.claude/settings.json` for every project, or `.claude/settings.json` for one project.
2. In the command, replace `SLOP_LINTER_DIR` with the full path to your clone. Escape backslashes in JSON (`C:\\tools\\slop-linter`).
3. If Vale isn't on the `PATH` of the shell that Claude Code starts, add `-Vale` with the full path to `vale.exe`.

You can change the hook's behavior with a parameter on the hook command or an environment variable:

- `-ProseDir` or `SLOP_LINTER_PROSE_DIR`: the folder name that marks prose. The default is `Writing`. Use `*` to lint every `.md` and `.txt` file Claude writes.
- `-ProseSkip` or `SLOP_LINTER_PROSE_SKIP`: comma-separated subfolder names to leave alone. The default is `reference,_archive`.
- `-Vale` or `VALE_BIN`: the path to `vale.exe`, when Vale isn't on `PATH`.
- `-LocalConfig` or `SLOP_LINTER_LOCAL_CONFIG`: a config path relative to a project root, such as `.vale-local.ini`. When a folder above the edited file has it, the hook uses that config instead of this repo's, so a project can keep its own vocabulary or rule settings.

For example, this `command` value lints prose anywhere under a folder named `docs`:

```json
"command": "powershell -NoProfile -ExecutionPolicy Bypass -File \"C:\\tools\\slop-linter\\hook\\vale-hook.ps1\" -ProseDir docs"
```

The hook is written for Windows PowerShell 5.1. It hasn't been tested under PowerShell 7 (`pwsh`) on macOS or Linux.

## Check that a cleanup only touched comments

Vale can't tell whether a comment is true. Comments that restate the code, stale docstrings, and comments that contradict the code need a human or an LLM to read them. If you hand that job to an LLM, `tools/comment_guard.py` checks that it changed comments and nothing else:

```sh
python tools/comment_guard.py ORIGINAL_FILE EDITED_FILE
```

Keep a copy of each file before the edit, and compare against it. The guard supports `.ps1`, `.psm1`, `.py`, and JavaScript and TypeScript files. It fails if the line endings, the BOM, directive comments (`noqa`, `#Requires`, `eslint-disable`, and similar), or any code token changed.

- In Python, it also locks docstrings that users see: FastAPI route handlers, Pydantic models, and a module docstring that the file reads through `__doc__`.
- If a program parses data out of a comment block, like a YAML manifest, add `--protect START END` with the block's opening and closing marker text. The guard then fails if anything between the markers changed. You can repeat `--protect` for more than one kind of block.
- JavaScript and TypeScript checks need Node.js and a `typescript` package. The guard finds it through the `SLOP_TS_MODULE` environment variable or the nearest `node_modules`.

## Lint commit messages

`tools/commit_lint.py` flags commit messages that restate the diff instead of giving the reason, and messages that carry an AI tool's fingerprints. It doesn't enforce a style. "fixed memory leak in Atomics.store (#537)", "redis-cli: fix #5096 double error message.", and a kernel-style body with trailers all pass.

It works in three tiers:

- Attribution always blocks: a `Co-Authored-By` or `Signed-off-by` trailer naming an AI tool, `Assisted-by` and similar disclosure trailers, "Generated with Claude Code" lines, the robot emoji, Replit agent trailers, and agent author names like `(aider)` or `devin-ai-integration[bot]`. Mentioning Claude or an LLM in ordinary prose doesn't count.
- Weak tells add up to a score: a body of bullets that mirror the changed files, a list of file names, "for better readability" and similar benefit tails, "This commit introduces", Markdown in the body, a long body for a tiny diff, a claim of tests when no test file changed, and a body with no reason in it. First person, a real reference like `Reported-by:` or a revert, a measurement, or a quoted error lowers the score. A score of 4 warns and 8 blocks.
- History reports style across many commits: which commits scored highest, whether every commit has the same shape, and where the style changed suddenly, which is often where an AI tool started writing the messages.

```sh
python tools/commit_lint.py .git/COMMIT_EDITMSG    # as a commit-msg hook
python tools/commit_lint.py --commit HEAD           # one commit
python tools/commit_lint.py --range main..HEAD      # each commit in a range, report only
python tools/commit_lint.py --history 200           # the last 200 commits, report only
```

To run it on every commit, call it from `.git/hooks/commit-msg` with the message file git passes as `$1`. A repo can set its own thresholds, turn off rules, or allow a trailer it wants to keep in `.devkit/commit-lint.json`:

```json
{"warn": 4, "block": 8, "disable": ["backticks"], "allow_trailers": ["Assisted-by"]}
```

Claude Code adds a co-author trailer and a "Generated with" line by default. Set `"attribution": {"commit": "", "pr": ""}` in `~/.claude/settings.json` to turn both off. In VS Code, set `git.addAICoAuthor` to `off` to stop the Copilot co-author trailer.

## Rule levels

Each rule has one of three levels:

- `error`: almost always an AI tell. Examples are "delve", "serves as a", chatbot phrases ("I hope this helps"), hook openers ("Have you ever wondered"), a trailing ", highlighting", and more than two em dashes in one paragraph.
- `warning`: likely a tell. Examples are filler, hedges, transition words, LinkedIn-isms, a single em dash, Title Case subheadings, and bold-header lists.
- `suggestion`: patterns that good writers also use, like "not X, it's Y", "Here's the thing", "genuinely", and an uncontracted "is not". Vale shows them, but they never block.

The hook runs with `--minAlertLevel=warning`, so errors and warnings block and suggestions only inform. On the command line, Vale exits with a nonzero code only for errors. To see suggestions, run Vale with `--minAlertLevel=suggestion` or `run-qa.ps1 -Level suggestion`.

## Tune it to your writing

The rules started as one writer's taste. Tune them to yours before you trust them. Your best published writing has to lint clean. If a rule flags a sentence you'd publish as is, the rule is wrong.

1. Put copies of a few pieces you're happy with in a scratch folder.
2. Run `vale --config=SLOP_LINTER_DIR/.vale.ini fix --apply` on the copies to straighten curly quotes, then lint them with `--minAlertLevel=warning`. `fix` is an unlisted command in Vale 3.22. If your version doesn't have it, straighten the quotes by hand.
3. For each hit, decide whether the rule or the writing is wrong. If it's the rule, fix it: narrow the regex, add an exception (a proper noun to `HeadingCase.yml`, for example), drop the level to `suggestion`, or turn the rule off for that file type in `.vale.ini`.
4. Repeat until the clean set returns zero warnings and zero errors.
5. Run the rules against drafts you know are weak. Most of those hits should be real.

Rerun steps 2 through 4 after every rule change. If a change makes the clean set fail, it's a regression.

## Add a rule

Every rule here exists because the same thing got cut out of an AI draft twice. When you edit an AI draft, compare your version with the original. A pattern you cut twice is a candidate.

1. Add a YAML file to `styles/NoSlop/` (prose and comments) or `styles/NoSlopCode/` (comments only). Most rules use Vale's `existence` or `substitution` checks. See the [Vale styles documentation](https://vale.sh/docs/styles) for the rest.
2. Add a line that triggers it to `tests/slop-sample.md` or `tests/slop-sample.py`.
3. Run the tests:

   ```sh
   python tests/run_tests.py
   ```

   The script checks that every rule fires at least once on the samples, and that `tests/should-pass.md` and `tests/should-pass.py` produce zero alerts. Those two files are ordinary technical writing. If your rule flags them, narrow it. If you find a false positive in the wild, add the sentence to one of them.

To cut a release, run `python tools/build_release.py` and attach `dist/NoSlop.zip` and `dist/NoSlopCode.zip` to a GitHub release.

Commas inside a `TokenIgnores` or `BlockIgnores` regex in `.vale.ini` split the value. Write `+?` instead of `{1,400}`.

## Code comments

For the file types listed in `.vale.ini` (Python, JavaScript, TypeScript, PowerShell, Go, Rust, C, C#, Java, Ruby, Lua, and PHP), Vale pulls out comments and docstrings and lints only those. String literals aren't checked. Code files get both `NoSlop` and `NoSlopCode`, with the essay-only `NoSlop` rules (heading case, contractions, bold, semicolons, and others) turned off. `NoSlopCode` adds rules for narration ("Here we"), difficulty words ("simply"), "please", future tense, time-bombs ("as of now"), anthropomorphism ("the parser knows"), shouted caps, history in comments ("ported from"), and a 25-word sentence limit.

Known gaps:

- Vale 3.22 skips `.mjs`, `.cjs`, `.mts`, and `.cts` files even with the `[formats]` mapping. The hook and `run-qa.ps1` work around it by linting those files as `.js` or `.ts`. For a manual run, pipe the file through standard input: `Get-Content file.mjs | vale --config=SLOP_LINTER_DIR/.vale.ini --ext=.js`.
- `BlockIgnores` and `TokenIgnores` don't apply to code files, because Vale pulls out comments first. Filter protected comment blocks in your own tooling.
- `EmDashCount` counts per paragraph, not per file.
- In an aligned comment table, the widest row still flags `EmDash` if only one space separates it from the dash.

## Credits

The rule categories draw on Wikipedia's [Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) page, maintained by WikiProject AI Cleanup. The code-comment rules follow the [Google developer documentation style guide](https://developers.google.com/style), plus the 25-word sentence limit from ASD-STE100.

Built on [Vale](https://github.com/vale-cli/vale) by Joseph Kato, released under the MIT License. Vale isn't bundled with this repo.

## License

MIT. See [LICENSE](LICENSE).
