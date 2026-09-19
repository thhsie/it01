import json, pathlib, sys
from decimal import Decimal
from it01.tax import Facts, assess, from_json

def main() -> int:
  if len(sys.argv) != 2:
    print("usage: python -m it01 FACTS.json", file=sys.stderr)
    return 2
  try: figs = assess(from_json(Facts, json.loads(pathlib.Path(sys.argv[1]).read_text(), parse_float=Decimal)))
  except (OSError, ValueError) as e:
    print(f"error: {e}", file=sys.stderr)
    return 1
  ret = []
  for fig in figs: ret += [f"{fig.rule:<46}{fig.amt:>14,}"] + [f"  {s.section:<42}{s.url}" for s in fig.src]
  print("\n".join(ret))
  return 0

if __name__ == "__main__": sys.exit(main())
