#!/usr/bin/env python3
import os, sys, token, tokenize

CODE = {token.OP, token.NAME, token.NUMBER, token.STRING}

def stats(root:str) -> list[tuple[str, int, float]]:
  ret = []
  for path, _, files in os.walk(root):
    for name in sorted(f for f in files if f.endswith(".py")):
      with tokenize.open(fp := os.path.join(path, name)) as f: toks = [t for t in tokenize.generate_tokens(f.readline) if t.type in CODE]
      if loc := len({ln for t in toks for ln in range(t.start[0], t.end[0]+1)}): ret.append((os.path.relpath(fp, "."), loc, len(toks)/loc))
  return sorted(ret, key=lambda r: -r[1])

if __name__ == "__main__":
  table = stats(sys.argv[1] if len(sys.argv) > 1 else "it01")
  for fn, loc, density in table: print(f"{fn:40s} {loc:6d} {density:6.1f}")
  print(f"total lines: {(total := sum(r[1] for r in table))}")
  if (limit := int(os.getenv("MAX_LINE_COUNT", "-1"))) != -1 and total > limit: sys.exit(f"over {limit} lines")
