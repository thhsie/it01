import json, subprocess, sys, tempfile, unittest
from test.helpers import ROOT

def run(*args:str) -> subprocess.CompletedProcess:
  return subprocess.run([sys.executable, "-m", "it01", *args], cwd=ROOT, capture_output=True, text=True)

def assess(facts:str) -> subprocess.CompletedProcess:
  with tempfile.NamedTemporaryFile("w", suffix=".json") as f:
    f.write(facts)
    f.flush()
    return run(f.name)

REFUSED = [
  ("[]", "facts must be a JSON object"),
  ("{}", "missing facts ['resident']"),
  ('{"resident": true, "salry": 1}', "unknown facts ['salry']"),
  ('{"resident": 1}', "invalid resident 1 of type int"),
  ('{"resident": true, "salary": true}', "invalid salary True of type bool"),
  ('{"resident": true, "salary": "10"}', "invalid salary 10 of type str"),
  ('{"resident": true, "dependants": 1.5}', "invalid dependants 1.5 of type Decimal"),
  ('{"resident": true, "salary": -1}', "invalid salary -1"),
]

class TestCli(unittest.TestCase):
  def test_prints_figures_with_links(self):
    out = assess(json.dumps({"resident": True, "dependants": 1, "salary": 1200000})).stdout
    self.assertIn("total tax                         68,000", out)
    self.assertIn("First Schedule Part I                     https://www.mra.mu/download/ITAConsolidated.pdf#page=262", out)

  def test_refuses_bad_facts(self):
    for facts, msg in REFUSED:
      with self.subTest(facts):
        ret = assess(facts)
        self.assertEqual((ret.returncode, ret.stderr), (1, f"error: {msg}\n"))

  def test_usage(self): self.assertEqual(run().returncode, 2)

if __name__ == "__main__": unittest.main()
