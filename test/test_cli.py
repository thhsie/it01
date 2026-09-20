import json, subprocess, sys, tempfile, unittest
from test.helpers import ROOT

def run(*args:str) -> subprocess.CompletedProcess:
  return subprocess.run([sys.executable, "-m", "it01", *args], cwd=ROOT, capture_output=True, text=True)

def saved(text:str, suffix:str, *args:str) -> subprocess.CompletedProcess:
  with tempfile.NamedTemporaryFile("w", suffix=suffix) as f:
    f.write(text)
    f.flush()
    return run(*args, f.name)

def statement(text:str) -> subprocess.CompletedProcess: return saved(text, ".txt", "rows")

def assess(facts:str) -> subprocess.CompletedProcess: return saved(facts, ".json")

STATEMENT = """\
Date        Description        Debit       Credit      Balance
01/07/2025  Opening                                   1,000.00
02/07/2025  Salary                       5,000.00     6,000.00
03/07/2025  Rent               1,500.00               4,500.00
"""

OUTGOINGS = """\
Date        Description        Debit       Credit      Balance
01/07/2025  Opening                                   5,000.00
02/07/2025  Rent               1,500.00               3,500.00
03/07/2025  Fees                 200.00               3,300.00
04/07/2025  Card                 300.00               3,000.00
"""

REFUSED = [
  ("[]", "facts must be a JSON object"),
  ("{}", "missing facts ['resident']"),
  ('{"resident": true, "salry": 1}', "unknown facts ['salry']"),
  ('{"resident": 1}', "invalid resident 1 of type int"),
  ('{"resident": true, "salary": true}', "invalid salary True of type bool"),
  ('{"resident": true, "salary": "10"}', "invalid salary 10 of type str"),
  ('{"resident": true, "dependants": 1.5}', "invalid dependants 1.5 of type Decimal"),
  ('{"resident": true, "salary": -1}', "invalid salary -1"),
  ('{"resident": true, "business": []}', "business must be a JSON object"),
  ('{"resident": true, "business": {"sales": 1}}', "unknown business ['sales']"),
  ('{"resident": true, "business": {"assets": {}}}', "assets must be a JSON list"),
  ('{"resident": true, "business": {"assets": [{"kind": "computer"}]}}', "missing asset ['cost']"),
  ('{"resident": true, "business": {"assets": [{"kind": "boat", "cost": 1}]}}', "unknown kind boat"),
]

class TestCli(unittest.TestCase):
  def test_prints_figures_with_links(self):
    out = assess(json.dumps({"resident": True, "dependants": 1, "salary": 1200000})).stdout
    self.assertIn(f"{'total tax':<46}{'68,000':>14}", out)
    self.assertIn("First Schedule Part I                     https://www.mra.mu/download/ITAConsolidated.pdf#page=262", out)

  def test_refuses_bad_facts(self):
    for facts, msg in REFUSED:
      with self.subTest(facts):
        ret = assess(facts)
        self.assertEqual((ret.returncode, ret.stderr), (1, f"error: {msg}\n"))

  def test_reads_assets(self):
    out = assess(json.dumps({"resident": True, "business": {"gross_income": 100000, "assets": [{"kind": "computer", "cost": 80000}]}})).stdout
    self.assertIn(f"{'annual allowance on computer':<46}{'40,000':>14}", out)

  def test_usage(self):
    for args in ((), ("read",), ("rows",), ("credits",), ("read", "a", "b"), ("rows", "a", "b"), ("a", "b")):
      self.assertEqual(run(*args).returncode, 2, args)

  def test_prints_transactions_with_their_check(self):
    out = statement(STATEMENT).stdout
    self.assertIn(f"{'02/07/2025':<12}{'':>14}{'5,000.00':>14}{'6,000.00':>14}  {'ok':<15}Salary", out)

  def test_says_so_when_nothing_was_paid_in(self):
    out = saved(OUTGOINGS, ".txt", "credits")
    self.assertEqual((out.returncode, out.stdout.strip()), (0, "no money was paid into the account"))

  def test_refuses_a_statement_it_cannot_check(self):
    ret = statement("Salary 5,000.00\nRent 1,500.00\n")
    self.assertEqual((ret.returncode, ret.stderr), (1, "error: no running balance column in the statement\n"))

if __name__ == "__main__": unittest.main()
