import json, pathlib, sys
from decimal import Decimal
from it01.read import read
from it01.tax import Facts, assess, from_json

def main() -> int:
  args = sys.argv[1:]
  reading = args[:1] == ["read"]
  rest = args[1:] if reading else args
  if len(rest) != 1:
    print("usage: python -m it01 FACTS.json\n       python -m it01 read DOCUMENT.txt", file=sys.stderr)
    return 2
  ret = []
  try:
    text = pathlib.Path(rest[0]).read_text()
    if reading:
      for p in read(text): ret += [f"{p.fact:<46}{p.amt:>14,}", f"  {p.quote}"]
      ret = ret or ["no facts found in the document"]
    else:
      for fig in assess(from_json(Facts, json.loads(text, parse_float=Decimal))):
        ret += [f"{fig.rule:<46}{fig.amt:>14,}"] + [f"  {s.section:<42}{s.url}" for s in fig.src]
  except (OSError, ValueError) as e:
    print(f"error: {e}", file=sys.stderr)
    return 1
  print("\n".join(ret))
  return 0

if __name__ == "__main__": sys.exit(main())
