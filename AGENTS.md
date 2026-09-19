# AGENTS.md

These rules bind every change to this repository, whoever or whatever writes it. They are not suggestions. Where a rule is enforced by a tool, the tool is named; where it is not, the reviewer enforces it.

## Commands

```sh
pip install -e '.[linting]'
python -m ruff check .
python -m mypy
python -m unittest
python -m unittest test.test_style.TestStyle.test_comments
MAX_LINE_COUNT=3000 python sz.py
```

Every check must pass before a commit. There is no formatter. Do not run one.

## What this is

A local-first agent that prepares an individual's income tax. It reads the taxpayer's documents, proposes facts, and computes the tax from facts the taxpayer has confirmed.

> **A model never decides tax. It only turns documents into facts.**

## Philosophy

1. **Readability and low complexity are the goal. Line count is how we measure it.** `sz.py` counts lines that carry code and CI caps the package. Code golf is worse than the line it saves: never delete a newline, a type or a name to fit the budget.
2. **Every line earns its place.** Deleting code is a contribution. Code that nothing calls, scaffolding for a future feature, and refactors done in expectation of something are rejected.
3. **Fix the root cause.** No special case, no `if` that patches one input, no workaround that happens to pass. Never edit or delete a test to make it pass.
4. **Complexity is never worth speed.** A speedup must be measured with a benchmark anyone can rerun, and should also simplify.
5. **Data over code.** Rates, bands, thresholds, reliefs and deadlines are tables. One small interpreter reads them. A new tax year is a new table, not new logic.
6. **Zero runtime dependencies.** The package imports the standard library and itself, nothing else. A small utility is written, not installed.
7. **The taxpayer's data never leaves the machine unless they point it somewhere.** Exactly one module, `it01/llm.py`, may use the network, and only to reach the model endpoint the user configures. No telemetry, no update checks, no analytics, no crash reports. Ever.
8. **You vouch for every line you submit.** If you could not explain each line when asked, do not submit it.

## Logic

1. **Two layers, one boundary.** Extraction is non-deterministic: it reads a document and proposes typed facts, each with the text it came from. Computation is deterministic: plain code that takes confirmed facts and a taxpayer profile and returns a result. Nothing a model outputs reaches computation without the taxpayer's confirmation. A model never computes an amount and never chooses a rule.
2. **Money is `Decimal`. Never `float`, anywhere in `it01/`.** Parse with `Decimal(str)`, and JSON with `json.loads(s, parse_float=Decimal)`. Round only where the law requires it, with the rounding it specifies, in one place.
3. **Computation is pure.** No IO, no clock, no environment, no randomness. The same facts give the same result, byte for byte.
4. **Every computed figure carries its provenance.** The result names the rule that produced it and the legal source that rule implements. A figure without a source is a bug.
5. **Each tax year's parameters live in their own table.** Changing a past year is a bug fix. It cites the source and comes with a test.
6. **Refuse rather than guess.** An unsupported case raises an error naming what is unsupported. Never default silently, never approximate.
7. **Bad input raises. Impossible states assert.** `assert` is stripped under `-O`, so it only guards invariants the code itself establishes.

## Code

### Layout
- Two-space indentation. Lines up to 150 characters. `ruff`, `test_two_space_indent`.
- At most one blank line anywhere. Zero or one between definitions. `test_single_blank_lines`.
- A body that is one statement goes on the header line: `def cdiv(a:int, b:int) -> int: return -(-a//b)`, `if amt <= 0: return ZERO`.
- No semicolons. No lambda bound to a name; write a one-line `def`. `ruff E702 E703 E731`.
- Annotations are tight, return arrows are spaced: `def tax(inc:Decimal, ty:int=2026) -> Decimal:`. Keyword arguments have no spaces: `f(a=1)`. `test_tight_annotations`, `ruff E251`.
- Imports are absolute. Standard library first on one line, `import os, re, sys`, then `from x import a, b`. No star imports, no `__all__`. `ruff F403 TID252`.
- f-strings only. Double quotes by default. `ruff UP031 UP032`.
- Continue long expressions inside brackets, never with a backslash.

### Comments
- No comments by default. What the code does is told by its names, its types and its tests. Why it does it goes in the commit message.
- A comment is the rare exception, for a why that nothing else can carry: `# the law rounds down, not to nearest`. `test_comments`.
  - One line. Never two comment lines in a row.
  - At most ten words, written as `# text`.
  - Plain English only. No dashes, no acronyms, no identifiers, no codes, no labels like `NOTE`, `TODO` or `RULE`.
- No docstrings. `test_no_docstrings`.
- A shebang on line 1, `# noqa: CODE` and `# type: ignore[code]` are not comments and are exempt. Avoid them anyway; a new suppression needs a reason in the commit message.

### Names
- Modules are one short lowercase word. Classes are `PascalCase`, functions and variables `snake_case`, constants and environment flags `UPPER_CASE`. A flag's name is its environment key.
- Short names in short scopes, descriptive names in wide ones. House abbreviations: `ret` the value being built, `fxn` a callable, `ctx` a context, `src` a source, `amt` an amount, `idx` an index, `cnt` a count.
- Predicates are `is_*`. Converters are `to_*` and `from_*`. A name says what a thing is or does, not how.
- `_` marks a private name. No getters, no setters.

### Patterns
- Records are `@dataclass(frozen=True)`. Change one with `dataclasses.replace`. A mutable dataclass is allowed only for a scratch accumulator named `*Ctx`. Stored collections are tuples. `test_frozen_dataclasses`.
- Closed sets are `Enum` with `auto()`. Compare members and `None` with `is`.
- Dispatch with data: a dict from key to function, or `match`. Not an `if`/`elif` ladder, not a class per case.
- Comprehensions, not `map` or `filter`. Use `:=` to capture and test. `next(gen, default)` to find the first. `a or b`, not `a if a else b`. `ruff C416 FURB110`.
- Functions over classes. A function exists when it is used in at least two places; a module when it is imported from at least two places or is a layer of its own.
- No `abc`. A base class names what a subclass must provide with `raise NotImplementedError("need x")`. Inheritance is at most two deep. `ruff TID251`.
- `@property` only for a derived value.
- Cache only when a measurement says to, and only pure functions of hashable arguments.
- Types everywhere in `it01/`. Builtin generics and `X|None`. Type aliases are plain assignments. `mypy`, `ruff UP006 UP007 UP035`.
- Configuration is environment flags declared in `it01/helpers.py`, and nowhere else reads the environment. No config classes, no config files. `test_env_only_in_helpers`.
- No `logging`. Diagnostics are `if DEBUG >= 2: print(...)`. `ruff TID251`.
- IO lives at the edges. `it01/helpers.py` imports nothing from `it01`. Imports flow one way, from low layers to high.
- Errors use built-in exception types. Messages are lowercase, name the offending value, and have no trailing period: `raise ValueError(f"unknown tax year {ty}")`. No bare `except`. `except Exception` only at the command-line boundary. `test_error_messages`, `ruff E722 BLE001`.

## Tests

- `unittest.TestCase`, run with `python -m unittest`. No test framework, no fixtures, no plugins.
- Every test file ends with `if __name__ == "__main__": unittest.main()`.
- A test checks one behaviour, in a few lines. Variants come from default arguments or a loop over a table, not copies.
- Test behaviour, not implementation. Official worked examples are the reference; a computation must match them exactly.
- Every bug fix ships a test that fails without the fix. A known bug is written as a test under `@unittest.expectedFailure`.
- Tests never touch the network or the clock, and seed any randomness.
- Duplication inside a test is fine when it keeps the test readable on its own.
- `test/test_style.py` and `test/test_privacy.py` encode rules of this file. Loosening one of them is a change to this file and needs its own PR.

## Commits and pull requests

- One pull request does one thing. A refactor is its own PR, goes first, and changes no computed result. The feature after it should be a few lines.
- Never mix whitespace, formatting or renames with a change in behaviour. Whitespace-only changes are not accepted.
- Read your diff before you open a PR. Delete everything that is not required.
- The PR description says, in one or two sentences, why the change should be merged.
- Commit subjects are lowercase, imperative and under 50 characters, with an optional `area:` prefix and no trailing period: `rates: add 2027 bands`, `remove unused rounding helper`.
- No trailers, no URLs, no signatures in commit messages.
- Do not amend or force-push a shared branch. Add a commit instead.
- `MAX_LINE_COUNT` is raised in its own commit, with the reason in the message.
