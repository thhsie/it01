import ast, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKIP = {"build", "dist"}

def sources(sub:str=".") -> dict[str, str]:
  paths = (p for p in (ROOT/sub).rglob("*.py") if not any(s.startswith(".") or s in SKIP for s in p.relative_to(ROOT).parts))
  return {p.relative_to(ROOT).as_posix(): p.read_text() for p in sorted(paths)}

def trees(sub:str=".") -> dict[str, ast.Module]: return {fn: ast.parse(src) for fn, src in sources(sub).items()}
