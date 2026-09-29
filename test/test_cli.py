import importlib, json, os, pathlib, subprocess, sys, tempfile, tomllib, unittest
from dataclasses import dataclass
from decimal import Decimal
from unittest import mock
from it01.__main__ import added, changed, questioned, responded, shaped, to_debits
from it01.labels import Labelled
from it01.keep import PAID_OUT, adrift, answer, case, fingerprint, keep, lines_of, loaded, offering, outgoing, priced
from it01.kinds import ADRIFT, paying, spoken
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

  def cased(self, paper:str, said:str) -> str:
    name = pathlib.Path(paper).name
    here = on_disk(json.dumps({"resident": True, "documents": {name: "payslip"}, "paths": {name: paper},
                               "texts": {fingerprint(said.encode()): name}}))
    self.addCleanup(os.unlink, here)
    return here

  def saved_document(self, said:str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f: f.write(said)
    self.addCleanup(os.unlink, f.name)
    return f.name

  def test_a_document_is_shown_as_the_engine_read_it(self):
    paper = self.saved_document(STATEMENT)
    ret = run("show", self.cased(paper, STATEMENT), pathlib.Path(paper).name)
    self.assertEqual((ret.returncode, ret.stdout), (0, STATEMENT))

  def test_a_document_the_case_never_read_cannot_be_shown(self):
    ret = run("show", self.cased("/nowhere/payslip.txt", ""), "other.txt")
    self.assertEqual((ret.returncode, ret.stderr), (1, "error: the case does not say where other.txt was read from\n"))

  def test_a_document_that_has_moved_says_where_it_was(self):
    ret = run("show", self.cased("/nowhere/payslip.txt", ""), "payslip.txt")
    self.assertEqual((ret.returncode, ret.stderr), (1, "error: payslip.txt is no longer at /nowhere/payslip.txt\n"))

  def test_a_document_rewritten_since_it_was_read_is_refused(self):
    paper = self.saved_document(OUTGOINGS)
    ret = run("show", self.cased(paper, STATEMENT), name := pathlib.Path(paper).name)
    self.assertEqual((ret.returncode, ret.stderr), (1, f"error: {name} has changed since it was read\n"))

  def test_usage(self):
    for args in ((), ("read",), ("rows",), ("credits",), ("debits",), ("keep",), ("local",), ("read", "a", "b"), ("keep", "a", "b"), ("a", "b"),
                 ("confirm",), ("confirm", "a"), ("confirm", "a", "b", "c"), ("add",), ("add", "a"), ("add", "a", "b", "c"),
                 ("show",), ("show", "a"), ("show", "a", "b", "c"),
                 ("answer",), ("answer", "a"), ("answer", "a", "b"), ("answer", "a", "b", "c", "d")):
      self.assertEqual(run(*args).returncode, 2, args)

  def test_a_document_already_read_is_not_read_again(self):
    name = on_disk(json.dumps({"resident": True, "documents": {"gone.txt": "payslip"}}))
    self.addCleanup(os.unlink, name)
    was = pathlib.Path(name).read_text()
    ret = run("add", name, "gone.txt")
    self.assertEqual((ret.returncode, pathlib.Path(name).read_text()), (0, was))
    self.assertIn("was read before", ret.stdout)

  def test_adding_a_statement_says_which_money_is_exempt_and_why(self):
    here = on_disk(json.dumps({"resident": True, "salary": 1200000}))
    self.addCleanup(os.unlink, here)
    found = (Labelled("05/07/2025", Decimal("12.50"), "Interest", "interest", Check.AGREES),)
    with mock.patch("it01.__main__.label", return_value=(found, ())): said = added(pathlib.Path(here), self.saved_document(STATEMENT))
    self.assertEqual(said[1:5], ["", "exempt", f"  {'interest':<32}{'12.50':>16}", f"    {'Second Schedule Part II Sub-Part B item 3(c)':<42}https://www.mra.mu/download/ITAConsolidated.pdf#page=267"])

  PAYMENT = "20,000.00 paid in on 12/01/2026, WALLET TRANSFER"

  def answered_with(self, said:str, keys:tuple[str, ...]=(f"bank.pdf, {PAYMENT}",), asking:str="what was this payment for", **given:object) -> dict:
    here = on_disk(json.dumps({"resident": True, "labels": dict.fromkeys(keys, "unclear"),
                               "pending": {self.PAYMENT: asking}} | given))
    self.addCleanup(os.unlink, here)
    responded(pathlib.Path(here), self.PAYMENT, said)
    return json.loads(pathlib.Path(here).read_text())

  FORMED = "1,107,000.00 on the line EMOLUMENTS NET OF EXEMPT INCOME 1,107,000.00"
  CHOICES = "which line of the form is this: net_emoluments (the net pay); total (the whole pay)"

  def answered_on_the_form(self, said:str, **given:object) -> dict:
    here = on_disk(json.dumps({"resident": True, "pending": {self.FORMED: self.CHOICES}} | given))
    self.addCleanup(os.unlink, here)
    responded(pathlib.Path(here), self.FORMED, said)
    return json.loads(pathlib.Path(here).read_text(), parse_float=Decimal)

  def test_a_form_answer_naming_a_line_that_feeds_a_fact_proposes_it(self):
    held = self.answered_on_the_form("net_emoluments")
    self.assertEqual((held["proposed"], held["sources"]["salary"]), ({"salary": Decimal("1107000.00")}, f"answered {self.FORMED}"))

  def test_a_form_answer_naming_a_line_that_feeds_nothing_moves_nothing(self):
    self.assertNotIn("proposed", self.answered_on_the_form("total"))

  def test_a_form_line_the_question_did_not_offer_is_refused(self):
    with self.assertRaisesRegex(ValueError, "with one of: net_emoluments, total"): self.answered_on_the_form("salary")

  def test_the_offered_lines_read_back_as_written(self):
    self.assertEqual(lines_of(offering("which line", (("net_emoluments", "the net pay, after exempt"), ("total", "all of it")))),
                     ["net_emoluments", "total"])

  def test_a_form_answer_for_a_confirmed_fact_becomes_a_question(self):
    held = self.answered_on_the_form("net_emoluments", salary=1000)
    self.assertIn("salary read as 1,107,000.00 in answered", next(iter(held["pending"])))

  def test_a_payment_answered_with_a_kind_is_relabelled_and_counted(self):
    held = self.answered_with("business")
    self.assertEqual((held["labels"], held["proposed"]), ({"bank.pdf, 20,000.00 paid in on 12/01/2026, WALLET TRANSFER": "business"},
                                                        {"business.gross_income": 20000}))
    self.assertIn("answered 20,000.00 paid in", held["sources"]["business.gross_income"])

  def test_a_payment_answered_with_a_kind_that_counts_nothing_is_only_relabelled(self):
    held = self.answered_with("other")
    self.assertEqual((list(held["labels"].values()), "proposed" in held), (["other"], False))

  def test_add_answering_another_question_is_kept_as_a_note(self):
    held = self.answered_with("add")
    self.assertEqual((held["answers"], "proposed" in held), ({self.PAYMENT: "add"}, False))

  def test_a_payment_answered_in_words_is_kept_as_a_note(self):
    held = self.answered_with("a gift from my sister")
    said = (list(held["labels"].values()), "proposed" in held, list(held["answers"].values()))
    self.assertEqual(said, (["unclear"], False, ["a gift from my sister"]))

  def test_identical_payments_in_one_statement_are_all_counted(self):
    held = self.answered_with("business", keys=(f"bank.pdf, {self.PAYMENT}", f"bank.pdf, {self.PAYMENT} (2)"))
    self.assertEqual((held["proposed"], set(held["labels"].values())), ({"business.gross_income": 40000}, {"business"}))

  def test_the_same_payment_in_two_statements_is_refused(self):
    with self.assertRaisesRegex(ValueError, "more than one document"):
      self.answered_with("business", keys=(f"a.pdf, {self.PAYMENT}", f"b.pdf, {self.PAYMENT}"))

  def test_a_payment_left_out_for_its_balance_stays_a_note(self):
    held = self.answered_with("noted", asking="the balance after this does not agree, so it is left out")
    self.assertEqual((list(held["labels"].values()), "proposed" in held), (["unclear"], False))

  def test_a_payment_left_out_for_its_balance_takes_only_noted(self):
    for asking in (ADRIFT, adrift()):
      with self.subTest(asking), self.assertRaisesRegex(ValueError, "with one of: noted"): self.answered_with("business", asking=asking)

  def test_a_case_without_labels_keeps_the_answer_as_a_note(self):
    held = self.answered_with("business", keys=())
    self.assertEqual((held["answers"], "proposed" in held), ({self.PAYMENT: "business"}, False))

  def test_a_payment_answered_with_a_kind_already_confirmed_becomes_a_question(self):
    held = self.answered_with("business", business={"gross_income": 100000})
    self.assertEqual(("proposed" in held, len(held["pending"])), (False, 1))

  def settled(self, said:str) -> tuple[dict, str]:
    here = on_disk(json.dumps({"resident": True, "business": {"gross_income": 100000}, "labels": {f"bank.pdf, {self.PAYMENT}": "unclear"},
                               "pending": {self.PAYMENT: "what was this payment for"}}))
    self.addCleanup(os.unlink, here)
    responded(pathlib.Path(here), self.PAYMENT, "business")
    responded(pathlib.Path(here), "business gross income", said)
    return json.loads(pathlib.Path(here).read_text()), pathlib.Path(here).read_text()

  def test_a_figure_already_confirmed_grows_only_when_the_answer_is_add(self):
    for said, gross in (("add", 120000), ("leave", 100000)):
      with self.subTest(said):
        held, _ = self.settled(said)
        self.assertEqual((held["business"]["gross_income"], "pending" in held), (gross, False))

  def test_a_figure_already_confirmed_is_answered_only_with_add_or_leave(self):
    with self.assertRaisesRegex(ValueError, "with one of: add, leave"): self.settled("yes please")

  def changed_to(self, first:str, then:str, **given:object) -> dict:
    here = on_disk(json.dumps({"resident": True, "labels": {f"bank.pdf, {self.PAYMENT}": "unclear"},
                               "pending": {self.PAYMENT: "what was this payment for"}} | given))
    self.addCleanup(os.unlink, here)
    responded(pathlib.Path(here), self.PAYMENT, first)
    changed(pathlib.Path(here), self.PAYMENT[:20], then)
    return json.loads(pathlib.Path(here).read_text())

  def test_a_changed_kind_moves_the_amount_to_the_new_fact(self):
    held = self.changed_to("business", "rent")
    self.assertEqual((held["proposed"], list(held["labels"].values()), held["answers"]), ({"rent": 20000}, ["rent"], {self.PAYMENT: "rent"}))
    self.assertEqual((list(held["sources"]), held["sources"]["rent"]), (["rent"], f"answered {self.PAYMENT}"))

  def test_a_kind_changed_to_one_that_counts_nothing_takes_the_amount_back(self):
    held = self.changed_to("business", "other")
    self.assertEqual(("proposed" in held, "sources" in held, list(held["labels"].values())), (False, False, ["other"]))

  def test_an_answer_in_words_can_become_a_kind(self):
    self.assertEqual(self.changed_to("a gift", "business")["proposed"], {"business.gross_income": 20000})

  def test_a_change_after_the_figure_was_confirmed_is_refused(self):
    here = on_disk(json.dumps({"resident": True, "labels": {f"bank.pdf, {self.PAYMENT}": "unclear"},
                               "pending": {self.PAYMENT: "what was this payment for"}}))
    self.addCleanup(os.unlink, here)
    responded(pathlib.Path(here), self.PAYMENT, "business")
    run("confirm", here, "business.gross_income")
    with self.assertRaisesRegex(ValueError, "is confirmed, so .* cannot be changed"): changed(pathlib.Path(here), self.PAYMENT, "rent")

  def test_a_change_to_a_kind_whose_fact_is_confirmed_becomes_a_question(self):
    held = self.changed_to("rent", "business", business={"gross_income": 100000})
    self.assertEqual(("business.gross_income" in held.get("proposed", {}), list(held["labels"].values())), (False, ["business"]))
    self.assertEqual(len(held["pending"]), 1)

  def test_only_a_kind_can_replace_an_answer(self):
    with self.assertRaisesRegex(ValueError, "only a payment's kind can be changed"): self.changed_to("business", "a gift")

  def test_a_question_not_yet_answered_cannot_be_changed(self):
    here = on_disk(json.dumps({"resident": True, "pending": {self.PAYMENT: "what was this payment for"}}))
    self.addCleanup(os.unlink, here)
    with self.assertRaisesRegex(ValueError, "0 answered questions match"): changed(pathlib.Path(here), self.PAYMENT, "rent")

  PENSION = (Labelled("03/07/2025", Decimal("1000.00"), "RETIREMENT PLAN", "pension", Check.AGREES),
             Labelled("03/08/2025", Decimal("1000.00"), "RETIREMENT PLAN", "pension", Check.UNCHECKED),
             Labelled("03/09/2025", Decimal("1000.00"), "RETIREMENT PLAN", "pension", Check.DIFFERS))

  def paid_out(self, spent:tuple[Labelled, ...], **given:object) -> tuple[str, dict]:
    here = on_disk(json.dumps({"resident": True, "salary": 1200000} | given))
    self.addCleanup(os.unlink, here)
    with mock.patch("it01.__main__.label", return_value=((), ())), mock.patch("it01.__main__.spending", return_value=spent):
      added(pathlib.Path(here), self.saved_document(STATEMENT))
    return here, json.loads(pathlib.Path(here).read_text())

  def test_every_question_a_statement_opens_lists_its_answers(self):
    table = spoken("labelling")
    both = (Check.AGREES, Check.DIFFERS)
    paid_in = tuple(Labelled("02/07/2025", Decimal("10.00"), f"IN {kind}", kind, check) for kind in table.prompt.kinds for check in both)
    debits = tuple(Labelled("03/07/2025", Decimal("20.00"), f"OUT {kind}", kind, Check.AGREES) for kind in paying().prompt.kinds)
    here = on_disk(json.dumps({"resident": True, "business": {"gross_income": 100000}}))
    self.addCleanup(os.unlink, here)
    with mock.patch("it01.credits.labelled", return_value=paid_in), mock.patch("it01.__main__.spending", return_value=debits):
      added(pathlib.Path(here), self.saved_document(STATEMENT))
    pending = json.loads(pathlib.Path(here).read_text())["pending"]
    self.assertGreater(len(pending), len(paying().prompt.kinds) - len(paying().aside))
    for question, asks in pending.items():
      with self.subTest(question): self.assertTrue(lines_of(asks) or asks in table.asking.values(), asks)

  def test_a_question_saved_before_its_answers_were_listed_shows_them(self):
    old = {"20.00 paid out in 1 payment that looks like housing loan, in a.pdf": "add the lender's certificate",
           "348.00 paid out in 7 payments that look like bills, in a.pdf": "add the business share of each bill to the accounts",
           "money labelled pay came in and the case gives no salary": "add the statement of emoluments",
           "10.00 paid in on 02/07/2025, IN rent": ADRIFT}
    shown = case(json.dumps({"resident": True, "pending": old}))["pending"]
    self.assertEqual([lines_of(asks) for asks in shown.values()], [["later", "not"], ["yes", "no"], ["not"], ["noted"]])

  def test_a_business_payment_takes_a_typed_share_up_to_its_total(self):
    spent = (Labelled("04/07/2025", Decimal("500.00"), "PHONE", "bills", Check.AGREES),)
    here, held = self.paid_out(spent, business={"gross_income": 100000})
    question = next(iter(held["pending"]))
    with self.assertRaisesRegex(ValueError, "from 0.01 to 500.00"): responded(pathlib.Path(here), question, "600")
    responded(pathlib.Path(here), question, "120.50")
    self.assertEqual(json.loads(pathlib.Path(here).read_text())["proposed"], {"business.utilities": 120.5})

  SUPPLIES = tuple(Labelled(f"0{n}/07/2025", Decimal(amt), f"SUPPLIER {n}", "business_expense", Check.AGREES)
                   for n, amt in ((4, "100.00"), (5, "250.50"), (6, "40.00")))

  def test_business_payments_are_kept_with_their_question_and_listed_by_number(self):
    here, held = self.paid_out(self.SUPPLIES, business={"gross_income": 100000})
    self.assertEqual([k.split(", ", 1)[1] for k in held["paid"]], [f"{amt} paid out on 0{n}/07/2025, SUPPLIER {n}" for n, amt in
                                                                    ((4, "100.00"), (5, "250.50"), (6, "40.00"))])
    self.assertIn("      2. 250.50 paid out on 05/07/2025, SUPPLIER 5", keep(pathlib.Path(here).read_text()))

  def test_payments_are_listed_only_for_a_question_that_takes_them_by_number(self):
    here, held = self.paid_out(self.PENSION)
    self.assertEqual(case(pathlib.Path(here).read_text())["payments"], {})
    self.assertEqual(len(held["paid"]), 2)
    self.assertNotIn("      1. ", "\n".join(keep(pathlib.Path(here).read_text())))

  def test_the_case_data_lists_the_payments_behind_a_question(self):
    here, held = self.paid_out(self.SUPPLIES, business={"gross_income": 100000})
    listed = case(pathlib.Path(here).read_text())["payments"][next(iter(held["pending"]))]
    self.assertEqual(listed, ["100.00 paid out on 04/07/2025, SUPPLIER 4", "250.50 paid out on 05/07/2025, SUPPLIER 5",
                              "40.00 paid out on 06/07/2025, SUPPLIER 6"])

  def test_a_payment_number_that_is_repeated_or_out_of_range_is_refused(self):
    here, held = self.paid_out(self.SUPPLIES, business={"gross_income": 100000})
    for wrong in ("payments 1, 1", "payments 4", "payment 0"):
      with self.subTest(wrong), self.assertRaisesRegex(ValueError, "payments 1 to 3"):
        responded(pathlib.Path(here), next(iter(held["pending"])), wrong)

  def test_the_payments_named_are_added_up_by_the_engine(self):
    for said, want in (("payments 1, 3", 140), ("payments 1, 2, 3", 390.5)):
      with self.subTest(said):
        here, held = self.paid_out(self.SUPPLIES, business={"gross_income": 100000})
        responded(pathlib.Path(here), next(iter(held["pending"])), said)
        self.assertEqual(json.loads(pathlib.Path(here).read_text())["proposed"], {"business.other_expenses": want})

  def test_a_case_saved_before_payments_were_kept_offers_no_numbers(self):
    question = "140.00 paid out in 2 payments that look like business expense, in bank.pdf"
    here = on_disk(json.dumps({"resident": True, "business": {"gross_income": 100000}, "pending": {question: "was this a cost of your business?"}}))
    self.addCleanup(os.unlink, here)
    with self.assertRaises(ValueError) as said: responded(pathlib.Path(here), question, "payments 1")
    self.assertNotIn("by number", str(said.exception))

  SALARY = "money labelled pay came in and the case gives no salary"

  def test_the_salary_question_closes_once_a_salary_is_proposed(self):
    text = json.dumps({"resident": True, "proposed": {"salary": 60000}, "pending": {self.SALARY: "add it", "cash of 1.00": "where from"}})
    self.assertEqual(loaded(answer(text, "cash of 1.00", "a gift")).get("pending", {}), {})
    self.assertNotIn(self.SALARY, case(text)["pending"])

  def test_the_salary_question_takes_only_the_answer_that_it_is_not_salary(self):
    here = on_disk(json.dumps({"resident": True, "pending": {self.SALARY: "add it"}}))
    self.addCleanup(os.unlink, here)
    with self.assertRaisesRegex(ValueError, "with one of: not"): responded(pathlib.Path(here), self.SALARY, "later")
    responded(pathlib.Path(here), self.SALARY, "not")
    self.assertEqual(json.loads(pathlib.Path(here).read_text()).get("pending", {}), {})

  def test_a_certificate_question_is_closed_without_moving_a_figure(self):
    spent = (Labelled("04/07/2025", Decimal("18000.00"), "HOME LOAN", "housing_loan", Check.AGREES),)
    for said in ("later", "not"):
      with self.subTest(said):
        here, held = self.paid_out(spent)
        responded(pathlib.Path(here), next(iter(held["pending"])), said)
        after = json.loads(pathlib.Path(here).read_text())
        self.assertEqual((after.get("pending", {}), "proposed" in after), ({}, False))

  def test_payments_out_of_one_kind_are_asked_about_once(self):
    _, held = self.paid_out(self.PENSION)
    question, asks = next(iter(held["pending"].items()))
    self.assertEqual((len(held["pending"]), question.split(", in ")[0]), (1, "2,000.00 paid out in 2 payments that look like pension"))
    self.assertIn("approved under the insurance law", asks)
    self.assertNotIn("proposed", held)

  def test_each_claim_question_names_its_kind_whatever_the_count(self):
    for kind in paying().claims:
      for cnt in (1, 2):
        with self.subTest(kind=kind, cnt=cnt):
          said = PAID_OUT.fullmatch(outgoing(Decimal("1500.00"), cnt, kind, "my, bank.pdf"))
          self.assertEqual((said["kind"].replace(" ", "_"), said["doc"]) if said else None, (kind, "my, bank.pdf"))

  def test_a_claim_question_offers_yes_and_no_with_what_each_adds(self):
    _, held = self.paid_out(self.PENSION)
    self.assertEqual(lines_of(next(iter(held["pending"].values()))), ["yes", "no"])

  def test_a_yes_proposes_the_relief_and_a_no_proposes_nothing(self):
    for said, proposed in (("yes", {"pension_contributions": 2000}), ("no", {})):
      with self.subTest(said):
        here, held = self.paid_out(self.PENSION)
        question = next(iter(held["pending"]))
        responded(pathlib.Path(here), question, said)
        after = json.loads(pathlib.Path(here).read_text())
        self.assertEqual(after.get("proposed", {}), proposed)
        if proposed: self.assertEqual(after["sources"]["pension_contributions"], f"answered {question}")

  def test_a_relief_question_takes_only_yes_or_no(self):
    here, held = self.paid_out(self.PENSION)
    with self.assertRaisesRegex(ValueError, "with one of: yes, no"): responded(pathlib.Path(here), next(iter(held["pending"])), "maybe")

  def test_a_relief_question_is_priced_from_the_confirmed_facts(self):
    here, held = self.paid_out(self.PENSION)
    prices = priced(pathlib.Path(here).read_text())[next(iter(held["pending"]))]
    self.assertEqual((prices["yes"].amt, prices["no"].amt), (Decimal("-400"), Decimal("0")))

  def test_business_payments_are_asked_about_only_with_a_business(self):
    spent = (Labelled("04/07/2025", Decimal("500.00"), "STOCK", "business_expense", Check.AGREES),)
    for given, asked in (({}, 0), ({"business": {"gross_income": 100000}}, 1)):
      with self.subTest(given): self.assertEqual(len(self.paid_out(spent, **given)[1].get("pending", {})), asked)

  def test_a_certificate_is_asked_for_where_the_statement_cannot_give_the_figure(self):
    spent = (Labelled("04/07/2025", Decimal("18000.00"), "HOME LOAN", "housing_loan", Check.AGREES),)
    self.assertIn("gives the interest paid in the year", next(iter(self.paid_out(spent)[1]["pending"].values())))

  def test_pay_in_two_statements_asks_once(self):
    here = on_disk(json.dumps({"resident": True}))
    self.addCleanup(os.unlink, here)
    found = (Labelled("02/07/2025", Decimal("5000.00"), "Salary", "pay", Check.AGREES),)
    with mock.patch("it01.__main__.label", return_value=(found, ())):
      for said in (STATEMENT, STATEMENT + "\n"): added(pathlib.Path(here), self.saved_document(said))
    self.assertEqual(len(json.loads(pathlib.Path(here).read_text())["pending"]), 1)

  def test_pay_in_the_bank_asks_for_the_salary_only_when_the_case_has_none(self):
    found = (Labelled("02/07/2025", Decimal("5000.00"), "Salary", "pay", Check.AGREES),)
    for given, asked in (({}, 1), ({"salary": 1200000}, 0), ({"proposed": {"salary": 1200000}}, 0)):
      here = on_disk(json.dumps({"resident": True} | given))
      self.addCleanup(os.unlink, here)
      with self.subTest(given), mock.patch("it01.__main__.label", return_value=(found, ())): added(pathlib.Path(here), self.saved_document(STATEMENT))
      pending = json.loads(pathlib.Path(here).read_text()).get("pending", {})
      self.assertEqual(len([q for q in pending if "the case gives no salary" in q]), asked)

  def test_the_same_file_under_another_name_is_not_read_twice(self):
    said = "Total emoluments        1,107,000.00\n"
    was = json.dumps({"resident": True, "documents": {"payslip.txt": "payslip"}, "texts": {fingerprint(said.encode()): "payslip.txt"}})
    name = on_disk(was)
    self.addCleanup(os.unlink, name)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f: f.write(said)
    self.addCleanup(os.unlink, paper := f.name)
    ret = run("add", name, paper)
    self.assertEqual((ret.returncode, pathlib.Path(name).read_text()), (0, was))
    self.assertIn("same file as payslip.txt", ret.stdout)

  def test_a_copy_is_refused_before_it_is_read(self):
    here = on_disk(json.dumps({"resident": True, "texts": {fingerprint(STATEMENT.encode()): "first.txt"}}))
    self.addCleanup(os.unlink, here)
    with mock.patch("it01.__main__.source", side_effect=AssertionError("read")):
      said = added(pathlib.Path(here), self.saved_document(STATEMENT))
    self.assertIn("same file as first.txt", said[0])

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

if __name__ == "__main__": unittest.main()
