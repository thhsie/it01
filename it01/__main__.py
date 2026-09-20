import json, pathlib, sys
from decimal import Decimal
from it01.read import read
from it01.rows import Check, entries
from it01.tax import Facts, assess, from_json

MARKS = {Check.AGREES: "ok", Check.DIFFERS: "does not agree", Check.UNCHECKED: "not checked"}
USAGE = "usage: python -m it01 FACTS.json\n       python -m it01 read DOCUMENT.txt\n       python -m it01 rows STATEMENT.txt"

def money(amt:Decimal|None) -> str: return f"{amt:,}" if amt is not None else ""

def to_figures(text:str) -> list[str]:
  ret = []
  for fig in assess(from_json(Facts, json.loads(text, parse_float=Decimal))):
    ret += [f"{fig.rule:<46}{fig.amt:>14,}"] + [f"  {s.section:<42}{s.url}" for s in fig.src]
  return ret

def to_proposals(text:str) -> list[str]:
  ret = []
  for p in read(text): ret += [f"{p.fact:<46}{p.amt:>14,}", f"  {p.quote}"]
  return ret or ["no facts found in the document"]

def to_transactions(text:str) -> list[str]:
  return [f"{e.date:<12}{money(e.paid_out):>14}{money(e.paid_in):>14}{money(e.balance):>14}  {MARKS[e.check]:<15}{e.description}"
          for e in entries(text)]

VERBS = {"read": to_proposals, "rows": to_transactions}

def main() -> int:
  args = sys.argv[1:]
  named = VERBS.get(args[0]) if args else None
  shape, rest = (named, args[1:]) if named else (to_figures, args)
  if len(rest) != 1:
    print(USAGE, file=sys.stderr)
    return 2
  try: lines = shape(pathlib.Path(rest[0]).read_text())
  except (OSError, ValueError) as e:
    print(f"error: {e}", file=sys.stderr)
    return 1
  print("\n".join(lines))
  return 0

if __name__ == "__main__": sys.exit(main())
