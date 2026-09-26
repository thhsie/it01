import ast, sys, tomllib, unittest
from test.helpers import ROOT, trees

NETWORK = {"asyncio", "ftplib", "http", "imaplib", "poplib", "smtplib", "socket", "socketserver", "ssl", "urllib", "webbrowser", "xmlrpc"}
NETWORK_ALLOWED = {"it01/llm.py"}
NETWORK_REACH_ALLOWED = {"it01/llm.py", "it01/read.py", "it01/credits.py", "it01/__main__.py"}
RUNTIME = {"numpy", "onnxruntime", "tokenizers"}
RUNTIME_ALLOWED = {"it01/local.py"}
PAPER = {"pypdf", "pypdfium2"}
PAPER_ALLOWED = {"it01/paper.py"}

def modules(tree:ast.Module) -> set[str]:
  names = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
  return names | {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}

def imports(tree:ast.Module) -> set[str]: return {m.split(".")[0] for m in modules(tree)}

def reaches(start:str, srcs:dict[str, ast.Module]) -> set[str]:
  seen, todo = set(), [start]
  while todo:
    if (fn := todo.pop()) in seen or fn not in srcs: continue
    seen.add(fn)
    todo += [f"{m.replace('.', '/')}.py" for m in modules(srcs[fn]) if m.startswith("it01.")]
  return seen

class TestPrivacy(unittest.TestCase):
  def test_no_dependencies(self): self.assertEqual(tomllib.loads((ROOT/"pyproject.toml").read_text())["project"]["dependencies"], [])

  def test_stdlib_only(self):
    for fn, tree in trees("it01").items():
      spare = (RUNTIME if fn in RUNTIME_ALLOWED else set()) | (PAPER if fn in PAPER_ALLOWED else set())
      self.assertEqual(imports(tree) - sys.stdlib_module_names - {"it01"} - spare, set(), fn)

  def test_runtime_only_in_local(self):
    for fn, tree in trees("it01").items():
      if fn not in RUNTIME_ALLOWED: self.assertEqual(imports(tree) & RUNTIME, set(), f"{fn} must not run a model")

  def test_the_runtime_is_an_extra(self):
    extras = tomllib.loads((ROOT/"pyproject.toml").read_text())["project"]["optional-dependencies"]
    for named, want in (("local", RUNTIME), ("pdf", PAPER)):
      with self.subTest(named): self.assertEqual({name.split(">")[0].split("=")[0] for name in extras[named]}, want)

  def test_a_document_reader_only_in_paper(self):
    for fn, tree in trees("it01").items():
      if fn not in PAPER_ALLOWED: self.assertEqual(imports(tree) & PAPER, set(), f"{fn} must not read a document format")

  def test_network_only_in_llm(self):
    for fn, tree in trees("it01").items():
      if fn not in NETWORK_ALLOWED: self.assertEqual(imports(tree) & NETWORK, set(), f"{fn} must not touch the network")

  def test_no_hidden_network_reach(self):
    srcs = trees("it01")
    for fn in srcs:
      if fn in NETWORK_REACH_ALLOWED: continue
      self.assertNotIn("it01/llm.py", reaches(fn, srcs), f"{fn} must not reach the network module through any import")

  def test_no_dynamic_imports(self):
    for fn, tree in trees("it01").items():
      calls = {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
      self.assertEqual(calls & {"__import__", "importlib.import_module"}, set(), fn)

if __name__ == "__main__": unittest.main()
