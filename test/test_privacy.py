import ast, sys, tomllib, unittest
from test.helpers import ROOT, trees

NETWORK = {"asyncio", "ftplib", "http", "imaplib", "poplib", "smtplib", "socket", "socketserver", "ssl", "urllib", "webbrowser", "xmlrpc"}
NETWORK_ALLOWED = {"it01/llm.py"}

def imports(tree:ast.Module) -> set[str]:
  names = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
  return {m.split(".")[0] for m in names | {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}}

class TestPrivacy(unittest.TestCase):
  def test_no_dependencies(self): self.assertEqual(tomllib.loads((ROOT/"pyproject.toml").read_text())["project"]["dependencies"], [])

  def test_stdlib_only(self):
    for fn, tree in trees("it01").items(): self.assertEqual(imports(tree) - sys.stdlib_module_names - {"it01"}, set(), fn)

  def test_network_only_in_llm(self):
    for fn, tree in trees("it01").items():
      if fn not in NETWORK_ALLOWED: self.assertEqual(imports(tree) & NETWORK, set(), f"{fn} must not touch the network")

  def test_no_dynamic_imports(self):
    for fn, tree in trees("it01").items():
      calls = {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
      self.assertEqual(calls & {"__import__", "importlib.import_module"}, set(), fn)

if __name__ == "__main__": unittest.main()
