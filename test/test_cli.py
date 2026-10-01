import importlib, json, pathlib, shutil, subprocess, sys, tempfile, tomllib, unittest
from dataclasses import dataclass
from decimal import Decimal
from unittest import mock
from it01.__main__ import accepted, added, dropped_doc, forgotten, rebuilt, responded, to_data, to_debits, yeared
from it01.asks import ADRIFT, proposals, questions, tables
from it01.held import Case, loaded, opened
from it01.labels import Labelled
from it01.rows import Check
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

INCOMINGS = """\
Date        Description        Debit       Credit      Balance
01/07/2025  Opening                                   1,000.00
02/07/2025  Salary                       5,000.00     6,000.00
03/07/2025  Interest                        12.50     6,012.50
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
  def setUp(self):
    quiet = mock.patch("it01.__main__.spending", return_value=())
    quiet.start()
    self.addCleanup(quiet.stop)

  def test_sheet_marks_what_the_return_fills_in_and_what_it_leaves_out(self):
    out = saved(json.dumps({"resident": True, "salary": 1200000, "other_income": 5}), ".json", "sheet").stdout
    self.assertIn(f"{'B_D_ENEXINC1':<24}{'1200000':>16}  filled in by the return, check it  the total of all rows", out)
    self.assertIn("  other_income has no field of its own", out)

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

  def test_debits_are_totalled_by_kind(self):
    found = (Labelled("03/07/2025", Decimal("1000.00"), "RETIREMENT PLAN", "pension", Check.AGREES),
             Labelled("03/08/2025", Decimal("1000.00"), "RETIREMENT PLAN", "pension", Check.UNCHECKED),
             Labelled("04/08/2025", Decimal("800.00"), "SHOP", "no_claim", Check.AGREES))
    with mock.patch("it01.__main__.spending", return_value=found): got = to_debits("")
    self.assertEqual(got, [f"{'pension':<46}{'2,000.00':>14}    2 debits, 1 with no balance that agrees",
                           f"{'no_claim':<46}{'800.00':>14}    1 debit"])

  def test_says_so_when_nothing_was_paid_out(self):
    out = saved(INCOMINGS, ".txt", "debits")
    self.assertEqual((out.returncode, out.stdout.strip()), (0, "no money was paid out of the account"))

  def test_each_transaction_names_the_line_it_starts_on(self):
    self.assertEqual([row.split()[0] for row in statement(STATEMENT).stdout.splitlines()], ["3", "4"])

  def test_refuses_a_statement_it_cannot_check(self):
    ret = statement("Salary 5,000.00\nRent 1,500.00\n")
    self.assertEqual((ret.returncode, ret.stderr), (1, "error: no running balance column in the statement\n"))

FORM = "Statement of emoluments\nfor the income year ended 30 June 2026\nNet emoluments 1,107,000.00\n"
YEAR = {"from": "2025-07", "to": "2026-06"}

def pay(date:str, amt:str, description:str, kind:str, check:Check=Check.AGREES) -> Labelled:
  return Labelled(date, Decimal(amt), description, kind, check)

WALLET = pay("13/07/2025", "20000.00", "WALLET TRANSFER", "unclear")
CLIENT = pay("15/07/2025", "500.00", "CLIENT", "business")
KEY = "bank.txt, 20,000.00 paid in on 13/07/2025, WALLET TRANSFER"
NET = Says(fact="salary", amt=Decimal("1107000.00"), quote="Net emoluments 1,107,000.00")
LINE = Says(amt=Decimal("1107000.00"), quote="EMOLUMENTS 1,107,000.00", asking="which line of the form is this",
            lines=(("net_emoluments", "the net pay"), ("total", "the whole pay")))
PLAIN = '{"resident": true}'

class TestCase(unittest.TestCase):
  def made(self, **given:object) -> pathlib.Path:
    here = pathlib.Path(on_disk(json.dumps({"resident": True} | given)))
    self.addCleanup(here.unlink, missing_ok=True)
    return here

  def paper(self, said:str, name:str="bank.txt") -> str:
    folder = tempfile.mkdtemp()
    self.addCleanup(shutil.rmtree, folder)
    (path := pathlib.Path(folder)/name).write_text(said)
    return str(path)

  def banked(self, here:pathlib.Path, found:tuple[Labelled, ...]=(), spent:tuple[Labelled, ...]=(), text:str=STATEMENT,
             name:str="bank.txt") -> list[str]:
    with mock.patch("it01.__main__.label", return_value=found), mock.patch("it01.__main__.spending", return_value=spent):
      return added(here, self.paper(text, name))

  def formed(self, here:pathlib.Path, told:tuple[Says, ...]=(NET,), asked:tuple[Says, ...]=(), text:str=FORM) -> list[str]:
    with mock.patch("it01.__main__.reading", return_value=(told, asked, ())): return added(here, self.paper(text, "soe.txt"))

  def held(self, here:pathlib.Path) -> Case: return opened(loaded(here.read_text()))

  def proposed(self, here:pathlib.Path) -> dict[str, Decimal]: return proposals(self.held(here), tables())[0]

  def waiting(self, here:pathlib.Path) -> list[str]:
    held = self.held(here)
    return [q.subject for q in questions(held, tables(), proposals(held, tables())[0]) if q.subject not in held.decisions]

  def asked(self, here:pathlib.Path, subject:str) -> list[str]:
    held = self.held(here)
    return [n for q in questions(held, tables(), proposals(held, tables())[0]) if q.subject == subject for n, _ in q.choices]

  def data(self, here:pathlib.Path) -> dict: return json.loads(to_data(here.read_text())[0])

  def test_an_unclear_payment_is_asked_about_and_counts_once_given_a_kind(self):
    self.banked(here := self.made(), (WALLET,))
    self.assertEqual(self.waiting(here), [KEY])
    responded(here, KEY, "business")
    self.assertEqual((self.waiting(here), self.proposed(here)), ([], {"business.gross_income": Decimal("20000.00")}))
    self.assertEqual(proposals(self.held(here), tables())[1]["business.gross_income"], "bank.txt, 1 labelled business")

  def test_a_kind_that_counts_nothing_proposes_nothing(self):
    self.banked(here := self.made(), (WALLET,))
    responded(here, KEY, "other")
    self.assertEqual((self.waiting(here), self.proposed(here)), ([], {}))

  def test_an_answer_that_is_not_offered_leaves_the_case_as_it_was(self):
    self.banked(here := self.made(), (WALLET,))
    was = here.read_text()
    with self.assertRaisesRegex(ValueError, "with one of: out, pay, business"): responded(here, KEY, "a gift")
    self.assertEqual(here.read_text(), was)

  def test_a_blank_subject_answers_nothing(self):
    ret = run("answer", str(here := self.made()), " ", "a gift")
    self.assertEqual((ret.returncode, ret.stderr, here.read_text()), (1, "error: name one of the questions, payments or readings\n", PLAIN))

  def test_two_payments_alike_but_for_the_wording_ask_two_questions(self):
    self.banked(here := self.made(), (WALLET, pay("13/07/2025", "20000.00", "WALLET TOPUP", "unclear")))
    self.assertEqual(len(self.waiting(here)), 2)

  def test_identical_payments_in_one_statement_are_each_counted(self):
    self.banked(here := self.made(), (CLIENT, CLIENT))
    self.assertEqual(self.proposed(here), {"business.gross_income": Decimal("1000.00")})
    self.assertEqual(list(self.held(here).payments)[1], "bank.txt, 500.00 paid in on 15/07/2025, CLIENT (2)")

  def test_a_payment_whose_balance_does_not_agree_is_left_out_until_answered(self):
    self.banked(here := self.made(), (pay("13/07/2025", "900.00", "RENT JULY", "rent", Check.DIFFERS),))
    key = "bank.txt, 900.00 paid in on 13/07/2025, RENT JULY"
    self.assertEqual((self.proposed(here), self.asked(here, key)), ({}, ["out", "pay", "business", "interest", "dividend", "rent", "other"]))
    responded(here, key, "rent")
    self.assertEqual(self.proposed(here), {"rent": Decimal("900.00")})
    responded(here, key, "out")
    self.assertEqual((self.proposed(here), self.waiting(here)), ({}, []))

  def test_a_left_out_payment_takes_any_kind(self):
    self.banked(here := self.made(), (pay("13/07/2025", "900.00", "RENT JULY", "rent", Check.DIFFERS),))
    responded(here, "bank.txt, 900.00 paid in on 13/07/2025, RENT JULY", "other")
    self.assertEqual((self.proposed(here), self.waiting(here)), ({}, []))

  def test_the_left_out_question_says_why(self):
    self.banked(here := self.made(), (pay("13/07/2025", "900.00", "RENT JULY", "rent", Check.DIFFERS),))
    self.assertEqual(self.data(here)["questions"][0]["asks"], ADRIFT)

  def test_a_confident_label_can_be_changed_and_then_forgotten(self):
    self.banked(here := self.made(), (CLIENT,))
    key = "bank.txt, 500.00 paid in on 15/07/2025, CLIENT"
    responded(here, key, "rent")
    self.assertEqual(self.proposed(here), {"rent": Decimal("500.00")})
    forgotten(here, key)
    self.assertEqual(self.proposed(here), {"business.gross_income": Decimal("500.00")})

  def test_nothing_said_cannot_be_forgotten(self):
    with self.assertRaisesRegex(ValueError, "0 answers match bank"): forgotten(self.made(), "bank")

  def test_a_relief_answer_can_change_from_yes_to_no(self):
    self.banked(here := self.made(), spent=(pay("13/07/2025", "200.00", "PENSION", "pension"),))
    responded(here, "bank.txt, paid out as pension", "yes")
    self.assertEqual(self.proposed(here), {"pension_contributions": Decimal("200.00")})
    responded(here, "bank.txt, paid out as pension", "no")
    self.assertEqual(self.proposed(here), {})

  def test_a_misread_form_figure_can_be_dropped_and_restored(self):
    self.formed(here := self.made())
    self.assertEqual(self.proposed(here), {"salary": Decimal("1107000.00")})
    responded(here, "soe.txt, salary", "wrong")
    self.assertEqual(self.proposed(here), {})
    forgotten(here, "soe.txt, salary")
    self.assertEqual(self.proposed(here), {"salary": Decimal("1107000.00")})

  def test_a_form_line_answer_proposes_the_fact_it_feeds(self):
    self.formed(here := self.made(), told=(), asked=(LINE,))
    subject = "soe.txt, 1,107,000.00 on the line EMOLUMENTS 1,107,000.00"
    self.assertEqual(self.asked(here, subject), ["net_emoluments", "total"])
    responded(here, subject, "net_emoluments")
    self.assertEqual(proposals(self.held(here), tables())[1], {"salary": f"answered {subject[9:]}, in soe.txt"})
    responded(here, subject, "total")
    self.assertEqual(self.proposed(here), {})
    with self.assertRaisesRegex(ValueError, "with one of: net_emoluments, total"): responded(here, subject, "salary")

  def test_a_new_reading_puts_a_confirmed_figure_back_to_the_person(self):
    self.banked(here := self.made(), (CLIENT,))
    accepted(here, "business.gross_income")
    self.assertEqual(self.proposed(here), {})
    self.banked(here, (pay("16/07/2025", "300.00", "CLIENT", "business"),), text=INCOMINGS, name="second.txt")
    got = self.data(here)
    self.assertEqual((got["proposed"], got["changed"]["business.gross_income"]["was"]), ({"business.gross_income": "800.00"}, "500.00"))

  def test_pay_in_the_bank_asks_for_the_salary_only_when_the_case_has_none(self):
    for given, asked in (({}, True), ({"salary": 1200000}, False)):
      self.banked(here := self.made(**given), (pay("13/07/2025", "5000.00", "SALARY", "pay"),))
      with self.subTest(given): self.assertEqual("money labelled pay" in self.waiting(here), asked)

  def test_the_salary_question_closes_once_a_salary_is_read(self):
    self.banked(here := self.made(), (pay("13/07/2025", "5000.00", "SALARY", "pay"),))
    self.formed(here)
    self.assertEqual(self.waiting(here), [])

  def test_money_that_was_not_pay_is_relabelled_as_what_it_was(self):
    self.banked(here := self.made(), (pay("13/07/2025", "5000.00", "TENANT", "pay"),))
    self.assertNotIn("pay", self.asked(here, "money labelled pay"))
    responded(here, "money labelled pay", "rent")
    self.assertEqual((self.proposed(here), self.waiting(here)), ({"rent": Decimal("5000.00")}, []))

  def test_pay_in_two_statements_asks_for_the_salary_once(self):
    self.banked(here := self.made(), (pay("13/07/2025", "5000.00", "SALARY", "pay"),))
    self.banked(here, (pay("13/08/2025", "5000.00", "SALARY", "pay"),), text=INCOMINGS, name="second.txt")
    self.assertEqual(self.waiting(here), ["money labelled pay"])

  def test_payments_out_of_one_kind_are_asked_about_once(self):
    self.banked(here := self.made(), spent=(pay("13/07/2025", "100.00", "PENSION", "pension"), pay("13/08/2025", "200.00", "PENSION", "pension")))
    self.assertEqual([(q["subject"], q["about"]) for q in self.data(here)["questions"]],
                     [("bank.txt, paid out as pension", "300.00 paid out in 2 payments that look like pension, in bank.txt")])

  def test_a_relief_question_takes_only_yes_or_no(self):
    self.banked(here := self.made(), spent=(pay("13/07/2025", "100.00", "PENSION", "pension"),))
    with self.assertRaisesRegex(ValueError, "with one of: yes, no$"): responded(here, "bank.txt, paid out as pension", "100")

  def test_a_relief_question_is_priced_from_the_figures_the_case_would_hold(self):
    self.banked(here := self.made(), (pay("13/07/2025", "900000.00", "CLIENT", "business"),), (pay("14/07/2025", "10000.00", "PENSION", "pension"),))
    prices = self.data(here)["questions"][0]["prices"]
    self.assertEqual((prices["yes"]["amount"], prices["no"]["amount"]), ("-1000", "0"))

  def test_a_certificate_question_moves_no_figure(self):
    self.banked(here := self.made(), spent=(pay("13/07/2025", "100.00", "INSURER", "medical_insurance"),))
    self.assertEqual(self.asked(here, "bank.txt, paid out as medical insurance"), ["later", "not"])
    responded(here, "bank.txt, paid out as medical insurance", "later")
    self.assertEqual((self.proposed(here), self.waiting(here)), ({}, []))

  def test_business_costs_without_income_ask_whether_there_is_a_business(self):
    self.banked(here := self.made(), spent=(pay("13/07/2025", "100.00", "OFFICE", "business_expense"),))
    self.assertEqual(self.waiting(here), ["bank.txt, business costs"])
    responded(here, "bank.txt, business costs", "business")
    self.assertEqual(self.waiting(here), ["bank.txt, paid out as business expense"])

  def test_costs_that_are_not_a_business_are_never_asked_about(self):
    self.banked(here := self.made(), spent=(pay("13/07/2025", "100.00", "OFFICE", "business_expense"),))
    responded(here, "bank.txt, business costs", "not")
    self.banked(here, (pay("14/07/2025", "500.00", "CLIENT", "business"),), text=INCOMINGS, name="second.txt")
    self.assertEqual(self.waiting(here), [])

  def test_costs_kept_from_an_earlier_statement_are_asked_about_once_income_comes_in(self):
    self.banked(here := self.made(), spent=(pay("13/07/2025", "100.00", "OFFICE", "business_expense"),))
    self.banked(here, (pay("14/07/2025", "500.00", "CLIENT", "business"),), text=INCOMINGS, name="second.txt")
    self.assertEqual(self.waiting(here), ["bank.txt, paid out as business expense"])

  def business(self) -> pathlib.Path:
    spent = (pay("13/07/2025", "100.00", "OFFICE", "business_expense"), pay("14/07/2025", "40.00", "PAPER", "business_expense"))
    self.banked(here := self.made(business={"gross_income": 1000}), spent=spent)
    return here

  def test_a_business_payment_takes_a_typed_share_up_to_its_total(self):
    responded(here := self.business(), "bank.txt, paid out as business expense", "60")
    self.assertEqual(self.proposed(here), {"business.other_expenses": Decimal("60")})
    with self.assertRaisesRegex(ValueError, "or the part that was, from 0.01 to 140.00"): responded(here, "bank.txt, paid out as business", "200")

  def test_payments_named_by_number_are_added_up(self):
    responded(here := self.business(), "bank.txt, paid out as business expense", "payments 1, 2")
    self.assertEqual(self.proposed(here), {"business.other_expenses": Decimal("140.00")})
    for said in ("payments 1, 1", "payments 3"):
      with self.subTest(said), self.assertRaisesRegex(ValueError, "naming each of payments 1 to 2 at most once"):
        responded(here, "bank.txt, paid out as business expense", said)

  def test_the_case_data_lists_the_payments_behind_a_business_question(self):
    got = self.data(self.business())["questions"][0]
    self.assertEqual(got["payments"], ["bank.txt, 100.00 paid out on 13/07/2025, OFFICE", "bank.txt, 40.00 paid out on 14/07/2025, PAPER"])

  def test_money_dated_outside_the_year_is_left_out_and_listed(self):
    said = self.banked(here := self.made(year=YEAR), (pay("15/05/2025", "900.00", "CLIENT", "business"), CLIENT))
    self.assertEqual(self.proposed(here), {"business.gross_income": Decimal("500.00")})
    self.assertEqual(said[1:4], ["", "left out, dated outside the income year", "  bank.txt, 900.00 paid in on 15/05/2025, CLIENT"])

  def test_a_new_year_counts_the_money_dated_in_it(self):
    self.banked(here := self.made(year=YEAR), (pay("15/05/2025", "900.00", "CLIENT", "business"), CLIENT))
    yeared(here, "2024-07")
    self.assertEqual(self.proposed(here), {"business.gross_income": Decimal("900.00")})

  def test_a_year_a_form_does_not_cover_is_refused(self):
    self.formed(here := self.made(year=YEAR))
    with self.assertRaisesRegex(ValueError, "soe.txt covers another income year"): yeared(here, "2024-07")

  def test_a_form_for_another_year_is_not_read(self):
    for said, why in (("for the income year ended 30 June 2025", "covers the income year ending 2025-06"),
                      ("", "does not say which income year it covers")):
      with self.subTest(said), self.assertRaisesRegex(ValueError, f"{why}, and this case covers 2025-07 to 2026-06"):
        self.formed(self.made(year=YEAR), text=f"Statement of emoluments {said}\nSalary 1,200.00\n")

  def test_a_payslip_is_not_read_as_the_form(self):
    ret = run("add", str(here := self.made()), self.paper("PAY STATEMENT\nPERIOD: June 2026\nNet Pay 90 552,00\n", "slip.txt"))
    self.assertIn("slip.txt is neither a bank statement nor a statement of emoluments", ret.stderr)
    self.assertEqual(here.read_text(), PLAIN)

  def test_a_statement_in_another_currency_than_the_case_is_not_read(self):
    self.banked(here := self.made(), text="Currency : ABC\n" + STATEMENT)
    self.assertEqual(self.held(here).documents["bank.txt"].currency, "ABC")
    with self.assertRaisesRegex(ValueError, "second.txt is in XYZ, and this case is in ABC, so nothing was read"):
      self.banked(here, text="Currency : XYZ\n" + STATEMENT, name="second.txt")

  def test_removing_a_document_takes_what_was_read_from_it_and_said_about_it(self):
    self.banked(here := self.made(), (WALLET,))
    responded(here, KEY, "business")
    accepted(here, "business.gross_income")
    dropped_doc(here, "bank.txt")
    held = self.held(here)
    self.assertEqual((held.documents, held.payments, held.decisions, self.proposed(here)), ({}, {}, {}, {"business.gross_income": Decimal(0)}))

  def test_a_rebuild_reads_every_document_again_and_keeps_every_answer(self):
    self.banked(here := self.made(), (WALLET, CLIENT))
    self.formed(here)
    for subject, said in ((KEY, "rent"), ("bank.txt, 500.00 paid in on 15/07/2025, CLIENT", "dividend"), ("soe.txt, salary", "wrong")):
      responded(here, subject, said)
    was = self.held(here)
    with mock.patch("it01.__main__.label", return_value=(WALLET, CLIENT)), mock.patch("it01.__main__.spending", return_value=()):
      with mock.patch("it01.__main__.reading", return_value=((NET,), (), ())): said = rebuilt(here)
    self.assertEqual((said, self.held(here)), ([f"{here.name} was read again from its documents"], was))

  def test_a_rebuild_names_the_answers_it_could_not_keep(self):
    self.banked(here := self.made(), (WALLET,))
    responded(here, KEY, "rent")
    with mock.patch("it01.__main__.label", return_value=()), mock.patch("it01.__main__.spending", return_value=()): said = rebuilt(here)
    self.assertEqual((said[-2:], self.held(here).decisions), (["answers not kept", f"  {KEY}"], {}))

  def test_a_rebuild_that_fails_leaves_the_case_and_no_spare_file(self):
    self.banked(here := self.made(), (WALLET,))
    was = here.read_text()
    with mock.patch("it01.__main__.label", side_effect=ValueError("the model could not read it")), self.assertRaisesRegex(ValueError, "could not"):
      rebuilt(here)
    self.assertEqual((here.read_text(), list(here.parent.glob(f"{here.name}.*"))), (was, []))

  def test_a_case_of_an_earlier_version_is_refused_until_it_is_read_again(self):
    paper = self.paper(STATEMENT)
    here = self.made(version={"case": "2"}, documents={"bank.txt": "bank statement"}, paths={"bank.txt": paper}, answers={"a question": "rent"})
    self.assertEqual(run("keep", str(here)).stderr, "error: a case of version 2 cannot be read\n")
    with mock.patch("it01.__main__.label", return_value=(WALLET,)), mock.patch("it01.__main__.spending", return_value=()): said = rebuilt(here)
    self.assertEqual((said[-1], list(self.held(here).payments)), ("  answers kept by an earlier version: 1", [KEY]))

  def test_a_case_whose_documents_are_gone_is_left_alone(self):
    here = self.made(version={"case": "2"}, documents={"bank.txt": "bank statement"}, paths={"bank.txt": "/nowhere/bank.txt"})
    was = here.read_text()
    with self.assertRaisesRegex(ValueError, "no longer there, so nothing changed: /nowhere/bank.txt"): rebuilt(here)
    self.assertEqual(here.read_text(), was)

  def test_a_document_with_no_recorded_path_stops_the_rebuild(self):
    with self.assertRaisesRegex(ValueError, "no recorded path, so nothing changed: bank.txt"):
      rebuilt(self.made(version={"case": "2"}, documents={"bank.txt": "bank statement"}))

  def test_confirming_moves_a_figure_into_the_facts(self):
    self.formed(here := self.made())
    ret = run("confirm", str(here), "salary")
    held = self.held(here)
    self.assertEqual((ret.returncode, held.given["salary"], held.confirmed, self.proposed(here)),
                     (0, Decimal("1107000.00"), {"salary": "1107000.00"}, {}))

  def test_confirming_a_figure_that_was_not_proposed_leaves_the_file_alone(self):
    ret = run("confirm", str(here := self.made()), "salary")
    self.assertEqual((ret.returncode, ret.stderr, here.read_text()), (1, "error: nothing is proposed for salary\n", PLAIN))

  def test_a_subject_is_answered_by_the_start_of_its_wording(self):
    self.banked(here := self.made(), (WALLET,))
    self.assertEqual(responded(here, "BANK.TXT, 20,000", "rent")[0], f"answered {KEY}")

  def test_a_wording_that_matches_no_subject_or_two_leaves_the_file_alone(self):
    self.banked(here := self.made(), (WALLET, CLIENT))
    was = here.read_text()
    for typed, cnt in (("nothing like it", 0), ("bank.txt", 2)):
      with self.subTest(typed), self.assertRaisesRegex(ValueError, f"^{cnt} questions, payments or readings match"): responded(here, typed, "rent")
    self.assertEqual(here.read_text(), was)

  def test_the_case_data_names_each_payment_with_its_label(self):
    self.banked(here := self.made(), (WALLET,))
    responded(here, KEY, "rent")
    got = self.data(here)["payments"][KEY]
    self.assertEqual((got["label"], got["read"], got["said"], got["month"]), ("rent", "unclear", "rent", "2025-07"))

  def test_adding_a_statement_says_which_money_is_exempt_and_why(self):
    said = self.banked(self.made(salary=1200000), (pay("05/07/2025", "12.50", "Interest", "interest"),))
    self.assertEqual(said[1:5], ["", "exempt", f"  {'interest':<32}{'12.50':>16}",
                                 f"    {'Second Schedule Part II Sub-Part B item 3(c)':<42}https://www.mra.mu/download/ITAConsolidated.pdf#page=267"])

  def test_a_document_is_shown_as_the_engine_read_it(self):
    self.banked(here := self.made())
    ret = run("show", str(here), "bank.txt")
    self.assertEqual((ret.returncode, ret.stdout), (0, STATEMENT))

  def test_a_document_the_case_never_read_cannot_be_shown(self):
    ret = run("show", str(self.made()), "other.txt")
    self.assertEqual((ret.returncode, ret.stderr), (1, "error: the case does not say where other.txt was read from\n"))

  def test_a_document_that_has_changed_or_moved_is_refused(self):
    self.banked(here := self.made())
    paper = pathlib.Path(self.held(here).documents["bank.txt"].path)
    paper.write_text(OUTGOINGS)
    self.assertEqual(run("show", str(here), "bank.txt").stderr, "error: bank.txt has changed since it was read\n")
    paper.unlink()
    self.assertEqual(run("show", str(here), "bank.txt").stderr, f"error: bank.txt is no longer at {paper}\n")

  def test_a_case_is_given_its_income_year(self):
    ret = run("year", str(here := self.made()), "2025-07")
    self.assertEqual((ret.returncode, json.loads(here.read_text())["year"]), (0, YEAR))

  def test_a_document_already_read_is_not_read_again(self):
    self.banked(here := self.made())
    was = here.read_text()
    self.assertEqual((self.banked(here, text=INCOMINGS)[0], here.read_text()), ("bank.txt was read before, so nothing changed", was))

  def test_the_same_file_under_another_name_is_not_read_twice(self):
    self.banked(here := self.made())
    with mock.patch("it01.__main__.source", side_effect=AssertionError("read")): said = self.banked(here, name="copy.txt")
    self.assertEqual(said, ["copy.txt is the same file as bank.txt, so nothing changed"])

  def test_usage(self):
    for args in ((), ("read",), ("rows",), ("credits",), ("debits",), ("keep",), ("local",), ("read", "a", "b"), ("keep", "a", "b"), ("a", "b"),
                 ("confirm",), ("confirm", "a"), ("confirm", "a", "b", "c"), ("add",), ("add", "a"), ("add", "a", "b", "c"),
                 ("show",), ("show", "a"), ("show", "a", "b", "c"), ("forget", "a"), ("forget", "a", "b", "c"),
                 ("answer",), ("answer", "a"), ("answer", "a", "b"), ("answer", "a", "b", "c", "d"), ("change", "a", "b", "c")):
      self.assertEqual(run(*args).returncode, 2, args)

if __name__ == "__main__": unittest.main()
