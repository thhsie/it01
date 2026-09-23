import importlib, json, os, pathlib, subprocess, sys, tempfile, tomllib, unittest
from dataclasses import dataclass
from decimal import Decimal
from it01.__main__ import questioned, shaped
from test.helpers import ROOT

@dataclass(frozen=True)
class Says:
  fact: str = ""
  amt: Decimal = Decimal(0)
  quote: str = ""
  line: str = ""
  asking: str = ""
  lines: tuple[tuple[str, str], ...] = ()
  date: str = ""
  description: str = ""

def run(*args:str) -> subprocess.CompletedProcess:
  return subprocess.run([sys.executable, "-m", "it01", *args], cwd=ROOT, capture_output=True, text=True)

def saved(text:str, suffix:str, *args:str) -> subprocess.CompletedProcess:
  with tempfile.NamedTemporaryFile("w", suffix=suffix) as f:
    f.write(text)
    f.flush()
    return run(*args, f.name)

def statement(text:str) -> subprocess.CompletedProcess: return saved(text, ".txt", "rows")

def on_disk(text:str) -> str:
  with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f: f.write(text)
  return f.name

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

LOST_PAGE = STATEMENT + """\
\fDate        Description        Debit       Credit
04/07/2025  Refund                          111.11
05/07/2025  Charges              222.22
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

  def test_says_how_many_amounts_a_page_lost(self):
    out = statement(LOST_PAGE).stdout
    self.assertIn("2 amounts on page 2 left out", out)
    self.assertIn("Rent", out)

  def test_a_cover_page_says_what_it_left_out(self):
    out = statement("Your statement\nOpening balance 1,000.00\nClosing balance 4,500.00\n\f" + STATEMENT).stdout
    self.assertIn("2 amounts on page 1 left out", out)
    self.assertIn("Rent", out)

  def test_a_credit_only_the_taxpayer_can_explain_becomes_a_question(self):
    questions = (Says(date="12/08/2025", amt=Decimal("1200.00"), description="CASH DEPOSIT", asking="where did this come from"),)
    self.assertEqual(questioned(questions), [("1,200.00 paid in on 12/08/2025, CASH DEPOSIT", "where did this come from")])

  def test_two_credits_alike_but_for_the_wording_ask_two_questions(self):
    both = (Says(date="12/08/2025", amt=Decimal("500.00"), description="CASH ONE", asking="where did this come from"),
            Says(date="12/08/2025", amt=Decimal("500.00"), description="CASH TWO", asking="where did this come from"))
    self.assertEqual(len(dict(questioned(both))), 2)

  def test_a_reading_becomes_figures_and_questions(self):
    told = (Says(fact="salary", amt=Decimal(1107000), quote="Total emoluments 1,107,000.00"),)
    asked = (Says(amt=Decimal(71401), quote="PAYE 71,401.00", asking="which line is this",
                  lines=(("tax_withheld", "tax taken off"), ("reliefs_claimed", "reliefs you claimed"))),)
    seen, asking = shaped(told, asked)
    self.assertEqual(seen, {"salary": (Decimal(1107000), "Total emoluments 1,107,000.00")})
    self.assertEqual(asking, [("71,401 on the line PAYE 71,401.00",
                               "which line is this: tax_withheld (tax taken off); reliefs_claimed (reliefs you claimed)")])

  def test_refuses_bad_facts(self):
    for facts, msg in REFUSED:
      with self.subTest(facts):
        ret = assess(facts)
        self.assertEqual((ret.returncode, ret.stderr), (1, f"error: {msg}\n"))

  def test_reads_assets(self):
    out = assess(json.dumps({"resident": True, "business": {"gross_income": 100000, "assets": [{"kind": "computer", "cost": 80000}]}})).stdout
    self.assertIn(f"{'annual allowance on computer':<46}{'40,000':>14}", out)

  def test_entry_point_resolves(self):
    spec = tomllib.loads((ROOT/"pyproject.toml").read_text())["project"]["scripts"]["it01"]
    where, name = spec.split(":")
    self.assertTrue(callable(getattr(importlib.import_module(where), name)))

  def test_the_types_are_shipped(self):
    shipped = tomllib.loads((ROOT/"pyproject.toml").read_text())["tool"]["setuptools"]["package-data"]["it01"]
    self.assertIn("py.typed", shipped)
    self.assertTrue((ROOT/"it01"/"py.typed").exists())

  def test_usage(self):
    for args in ((), ("read",), ("rows",), ("credits",), ("keep",), ("local",), ("read", "a", "b"), ("keep", "a", "b"), ("a", "b"),
                 ("confirm",), ("confirm", "a"), ("confirm", "a", "b", "c"), ("add",), ("add", "a"), ("add", "a", "b", "c"),
                 ("answer",), ("answer", "a"), ("answer", "a", "b"), ("answer", "a", "b", "c", "d")):
      self.assertEqual(run(*args).returncode, 2, args)

  def test_a_document_already_read_is_not_read_again(self):
    name = on_disk(json.dumps({"resident": True, "documents": {"gone.txt": "payslip"}}))
    self.addCleanup(os.unlink, name)
    was = pathlib.Path(name).read_text()
    ret = run("add", name, "gone.txt")
    self.assertEqual((ret.returncode, pathlib.Path(name).read_text()), (0, was))
    self.assertIn("was read before", ret.stdout)

  def test_confirming_moves_a_figure_into_the_facts(self):
    name = on_disk(json.dumps({"resident": True, "salary": 1200000, "proposed": {"other_income": 40000},
                               "sources": {"other_income": "Rent received 40,000.00"}}))
    self.addCleanup(os.unlink, name)
    ret = run("confirm", name, "other_income")
    held = json.loads(pathlib.Path(name).read_text())
    self.assertEqual((ret.returncode, held["other_income"], "proposed" in held), (0, 40000, False))
    self.assertIn("other_income", ret.stdout)

  def test_confirming_a_figure_that_was_not_proposed_leaves_the_file_alone(self):
    was = json.dumps({"resident": True, "salary": 1200000})
    name = on_disk(was)
    self.addCleanup(os.unlink, name)
    ret = run("confirm", name, "rent")
    self.assertEqual((ret.returncode, ret.stderr), (1, "error: nothing is proposed for rent\n"))
    self.assertEqual(pathlib.Path(name).read_text(), was)

  def test_answering_a_question_by_the_start_of_its_wording(self):
    asked = "1,200.00 paid in on 12/08/2025, CASH"
    name = on_disk(json.dumps({"resident": True, "salary": 1200000, "pending": {asked: "what is this money"}}))
    self.addCleanup(os.unlink, name)
    ret = run("answer", name, "1,200.00 PAID in", "sold my old bicycle")
    held = json.loads(pathlib.Path(name).read_text())
    self.assertEqual((ret.returncode, held["answers"][asked], "pending" in held), (0, "sold my old bicycle", False))
    self.assertIn("sold my old bicycle", ret.stdout)

  def test_a_wording_that_matches_no_question_or_two_leaves_the_file_alone(self):
    was = json.dumps({"resident": True, "pending": {"1,200.00 paid in, CASH": "what is this", "1,200.00 paid in, ATM": "what is this"}})
    for which, cnt in (("1,200.00", 2), ("900.00", 0), ("200", 0)):
      name = on_disk(was)
      self.addCleanup(os.unlink, name)
      with self.subTest(which):
        ret = run("answer", name, which, "a gift")
        self.assertEqual((ret.returncode, ret.stderr), (1, f"error: {cnt} open questions match {which}\n"))
        self.assertEqual(pathlib.Path(name).read_text(), was)

  def test_the_whole_wording_picks_the_question_it_is_the_start_of(self):
    short, long = "cash of 1,200.00", "cash of 1,200.00 on 12/08/2025"
    name = on_disk(json.dumps({"resident": True, "pending": {short: "what is this", long: "what is this"}}))
    self.addCleanup(os.unlink, name)
    ret = run("answer", name, short, "a gift")
    held = json.loads(pathlib.Path(name).read_text())
    self.assertEqual((ret.returncode, held["answers"], held["pending"]), (0, {short: "a gift"}, {long: "what is this"}))

  def test_a_blank_question_answers_nothing(self):
    was = json.dumps({"resident": True, "pending": {"1,200.00 paid in, CASH": "what is this"}})
    name = on_disk(was)
    self.addCleanup(os.unlink, name)
    ret = run("answer", name, "", "a gift")
    self.assertEqual((ret.returncode, ret.stderr), (1, "error: the question to answer is blank\n"))
    self.assertEqual(pathlib.Path(name).read_text(), was)

  def test_prints_transactions_with_their_check(self):
    out = statement(STATEMENT).stdout
    self.assertIn(f"{'02/07/2025':<12}{'':>14}{'5,000.00':>14}{'6,000.00':>14}  {'ok':<15}Salary", out)

  def test_the_record_holds_the_wording_and_the_law(self):
    out = saved(json.dumps({"resident": True, "salary": 1200000, "dependants": 1,
                            "sources": {"salary": "Total emoluments  1,200,000.00"}}), ".json", "keep").stdout
    self.assertIn("      Total emoluments  1,200,000.00", out)
    self.assertIn("First Schedule Part I", out)

  def test_the_same_key_written_twice_is_refused_everywhere(self):
    twice = '{"resident": true, "salary": 1, "salary": 2}'
    for verb in ((), ("keep",)):
      with self.subTest(verb):
        ret = saved(twice, ".json", *verb)
        self.assertEqual((ret.returncode, ret.stderr), (1, "error: the same key is written twice salary\n"))

  def test_a_facts_file_with_wording_still_computes(self):
    out = assess(json.dumps({"resident": True, "dependants": 1, "salary": 1200000,
                             "sources": {"salary": "Total emoluments  1,200,000.00"}}))
    self.assertEqual(out.returncode, 0)
    self.assertIn(f"{'total tax':<46}{'68,000':>14}", out.stdout)

  def test_says_so_when_nothing_was_paid_in(self):
    out = saved(OUTGOINGS, ".txt", "credits")
    self.assertEqual((out.returncode, out.stdout.strip()), (0, "no money was paid into the account"))

  def test_refuses_a_statement_it_cannot_check(self):
    ret = statement("Salary 5,000.00\nRent 1,500.00\n")
    self.assertEqual((ret.returncode, ret.stderr), (1, "error: no running balance column in the statement\n"))

if __name__ == "__main__": unittest.main()
