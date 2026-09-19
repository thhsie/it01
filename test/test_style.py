import ast, io, re, tokenize, unittest
from test.helpers import sources, trees

PRAGMA = re.compile(r"# (noqa: [A-Z]+[0-9]+|type: ignore\[[a-z-]+\])")
BODIES = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)

class TestStyle(unittest.TestCase):
  def test_no_comments(self):
    for fn, src in sources().items():
      for t in (t for t in tokenize.generate_tokens(io.StringIO(src).readline) if t.type is tokenize.COMMENT):
        if t.start != (1, 0) or not t.string.startswith("#!"): self.assertRegex(t.string, PRAGMA, f"{fn}:{t.start[0]}")

  def test_no_docstrings(self):
    for fn, tree in trees().items():
      for n in (n for n in ast.walk(tree) if isinstance(n, BODIES) and n.body):
        self.assertIsNone(ast.get_docstring(n, clean=False), f"{fn}:{getattr(n, 'lineno', 1)}")

  def test_single_blank_lines(self):
    for fn, src in sources().items(): self.assertNotIn("\n\n\n", src, fn)

  def test_two_space_indent(self):
    for fn, src in sources().items():
      depth = 0
      for t in tokenize.generate_tokens(io.StringIO(src).readline):
        if t.type is tokenize.INDENT: self.assertEqual(len(t.string), depth+2, f"{fn}:{t.start[0]}")
        if t.type in (tokenize.INDENT, tokenize.DEDENT): depth = len(t.line) - len(t.line.lstrip(" "))

  def test_tight_annotations(self):
    for fn, tree in trees().items():
      for a in (a for a in ast.walk(tree) if isinstance(a, ast.arg) and a.annotation):
        self.assertEqual((a.annotation.lineno, a.annotation.col_offset), (a.lineno, a.col_offset+len(a.arg)+1), f"{fn}:{a.lineno} write {a.arg}:T")

  def test_frozen_dataclasses(self):
    for fn, tree in trees().items():
      for c in (c for c in ast.walk(tree) if isinstance(c, ast.ClassDef) and not c.name.endswith("Ctx")):
        for d in (d for d in c.decorator_list if "dataclass" in ast.unparse(d)): self.assertIn("frozen=True", ast.unparse(d), f"{fn}:{c.lineno}")

  def test_error_messages(self):
    for fn, tree in trees().items():
      for r in (r for r in ast.walk(tree) if isinstance(r, ast.Raise) and isinstance(r.exc, ast.Call) and r.exc.args):
        msg = ast.unparse(r.exc.args[0]).lstrip("f").strip("'\"")
        self.assertFalse(re.match(r"[A-Z][a-z]", msg) or msg.endswith("."), f"{fn}:{r.lineno} lowercase, no trailing period")

  def test_env_only_in_helpers(self):
    for fn, src in sources("it01").items():
      if fn != "it01/helpers.py": self.assertNotRegex(src, r"\bos\.(environ|getenv)\b", fn)

  def test_no_float_in_package(self):
    for fn, tree in trees("it01").items():
      for n in ast.walk(tree):
        self.assertFalse(isinstance(n, ast.Constant) and isinstance(n.value, float), f"{fn}:{getattr(n, 'lineno', 0)} use Decimal")
        self.assertFalse(isinstance(n, ast.Name) and n.id == "float", f"{fn}:{getattr(n, 'lineno', 0)} use Decimal")

if __name__ == "__main__": unittest.main()
