import json, unittest
from dataclasses import replace
from decimal import Decimal
from it01.asks import EACH, OUT, SAME, Asked, balance, based, derived, months_of, priced, projected, proposals, questions, tables, year_of, yearly
from it01.asks import decided, label_of, payer, subject_of
from it01.held import VERSION, Case, Document, Line, Payment, Reading, dumped, loaded, opened, written
from it01.keep import ENTERED, answered, case, confirm, figures, forgot, keep, noted, received, removed, set_fact, shown, unconfirmed, with_year
from it01.keep import remember, said_to

T = tables()
BANK = Document("bank statement", "in/bank.txt", "a")
SOE = Document("statement of emoluments", "in/soe.txt", "b", ends="2026-06")

def paid(amt:str, kind:str, date:str="15/07/2025", way:str="in", check:str="ok", month:str|None="2025-07", doc:str="bank.txt") -> Payment:
  return Payment(doc, way, Decimal(amt), date, "CLIENT", kind, check, month)

def made(*paid_:Payment, read:tuple[Reading, ...]=(), **given:object) -> Case:
  held = opened({"resident": True} | given)
  held = noted(held, "bank.txt", BANK, [(f"{p.amount:,} paid {p.way} on {p.date}, {p.description}", p) for p in paid_], [], [])
  return noted(held, "soe.txt", SOE, [], list(read), []) if read else held

SALARY = Reading("soe.txt", "salary", Decimal("1107000.00"), "Net emoluments 1,107,000.00")

def proposed(held:Case) -> dict[str, Decimal]: return proposals(held, T)[0]

def broken(**records:object) -> dict:
  return {"resident": True, "version": VERSION, "documents": {"bank.txt": {"kind": "bank statement", "path": "p", "mark": "m"}}} | records

class TestKeep(unittest.TestCase):
  def test_the_record_holds_every_heading(self):
    held = made(paid("500.00", "business"), paid("700.00", "cash"), read=(SALARY,))
    ret = keep(held, T)
    for heading in ("facts that you accepted", "figures", "proposed figures to accept", "documents in the case",
                    "the type of each payment", "the figures read from each form", "questions with no answer"):
      with self.subTest(heading): self.assertIn(heading, ret)

  def test_a_fact_is_shown_with_the_wording_it_came_from(self):
    ret = keep(confirm(made(read=(SALARY,)), T, "salary"), T)
    self.assertEqual(ret[ret.index(next(line for line in ret if line.startswith("  salary"))) + 1], "      soe.txt, Net emoluments 1,107,000.00")

  def test_a_figure_is_shown_with_the_law_behind_it(self):
    ret = "\n".join(keep(made(salary=1200000), T))
    self.assertIn("  income tax", ret)
    self.assertIn("https://www.mra.mu/download/ITAConsolidated.pdf#page=26", ret)

  def test_an_answer_is_shown_under_its_subject(self):
    held = replace(made(paid("700.00", "cash")), decisions={"bank.txt, 700.00 paid in on 15/07/2025, CLIENT": "dividend"})
    ret = keep(held, T)
    at = ret.index("questions with an answer")
    self.assertEqual(ret[at + 1:at + 3], ["  bank.txt, 700.00 paid in on 15/07/2025, CLIENT", "      dividend"])

  def test_the_wording_never_reaches_the_computation(self):
    rich = made(paid("500.00", "business"), read=(SALARY,), business={"gross_income": 900000, "assets": [{"kind": "computer", "cost": 80000}]})
    self.assertEqual(figures({"resident": True, "business": {"gross_income": 900000, "assets": [{"kind": "computer", "cost": 80000}]}}),
                     figures(rich.given))

  def test_an_asset_that_produced_a_figure_is_in_the_record(self):
    ret = keep(made(business={"gross_income": 900000, "assets": [{"kind": "computer", "cost": 80000}]}), T)
    self.assertTrue(any(line.strip().startswith("kind") and "computer" in line for line in ret))
    self.assertTrue(any(line.startswith("  annual allowance on computer") for line in ret))

  def test_a_list_of_amounts_is_shown_one_amount_a_line(self):
    ret = keep(made(dependants=1, medical_insurance=[1000, 2000]), T)
    at = ret.index("  medical_insurance")
    self.assertEqual([line.split() for line in ret[at + 1:at + 3]], [["1", "1,000"], ["2", "2,000"]])

  def test_the_same_key_written_twice_is_refused(self):
    with self.assertRaisesRegex(ValueError, "the file has the same key two times cash"): loaded('{"decisions": {"cash": "a", "cash": "b"}}')

  def test_the_file_comes_back_the_way_it_went_in(self):
    held = replace(made(paid("500.00", "business"), paid("90.00", "pension", way="out", check="not checked"), read=(SALARY,)),
                   decisions={"bank.txt, paid out as pension": "yes"})
    held = noted(held, "form.txt", Document("statement of emoluments", "p", "c"), [],
                 [], [("1.00 on the line X", Line("form.txt", Decimal("1.00"), "X", "which line", (("total", "the whole pay"),)))])
    self.assertEqual(opened(loaded(written(held))), held)

  def test_a_case_file_cannot_hold_what_json_has_no_word_for(self):
    with self.assertRaisesRegex(ValueError, "a case file cannot have <object"): dumped({"a": object()})

  def test_a_record_that_does_not_hold_up_is_refused(self):
    good = {"document": "bank.txt", "way": "in", "amount": "5.00", "date": "15/07/2025", "description": "X", "label": "business", "check": "ok"}
    for records, says in (({"payments": {"k": good | {"colour": "red"}}}, r"payments k has unknown fields \['colour'\]"),
                          ({"payments": {"k": {n: v for n, v in good.items() if n != "label"}}}, r"payments k needs \['label'\] as text"),
                          ({"payments": {"k": good | {"way": "sideways"}}}, r"these payments have an unknown direction, check or month \['k'\]"),
                          ({"payments": {"k": good | {"check": "maybe"}}}, r"these payments have an unknown direction, check or month \['k'\]"),
                          ({"payments": {"k": good | {"month": "July"}}}, r"these payments have an unknown direction, check or month \['k'\]"),
                          ({"payments": {"k": good | {"amount": "five"}}}, "not an amount five"),
                          *(({"payments": {"k": good | {"line": bad}}}, "line as a number from 1") for bad in ("3", Decimal("1.5"), True, 0)),
                          ({"payments": {"k": good | {"document": "other.txt"}}}, r"these refer to a document that is not in the case \['k'\]"),
                          ({"readings": {"k": {"document": "bank.txt", "fact": "luck", "amount": "1", "quote": "q"}}}, r"unknown facts \['k'\]"),
                          ({"lines": {"k": {"document": "bank.txt", "amount": "1", "quote": "q", "asking": "a", "lines": {"x": 1}}}},
                           "lines k lines must be a JSON object of text"),
                          ({"confirmed": {"salary": "lots"}, "salary": 1}, r"confirmed has a figure that is not an amount \['salary'\]"),
                          ({"sources": {"salary": "a line"}}, r"sources and accepted figures refer to facts that are not in the case \['salary'\]"),
                          ({"decisions": {"k": " "}}, "decisions must be a JSON object of text"),
                          ({"payments": []}, "payments must be a JSON object")):
      with self.subTest(says), self.assertRaisesRegex(ValueError, says): opened(broken(**records))

  def test_a_case_of_another_version_is_refused(self):
    for raw, says in (({"version": {"case": "2"}}, "version 2"), ({"documents": {"a.txt": "payslip"}}, "version none")):
      with self.subTest(says), self.assertRaisesRegex(ValueError, f"cannot read a case of {says}"): opened({"resident": True} | raw)

  def test_a_case_with_only_a_year_needs_no_version(self):
    self.assertEqual(opened({"resident": True, "year": {"from": "2025-07", "to": "2026-06"}}).year, {"from": "2025-07", "to": "2026-06"})

  def test_confirming_records_the_value_and_where_it_came_from(self):
    held = confirm(made(read=(SALARY,)), T, "salary")
    self.assertEqual((held.given["salary"], held.confirmed, held.sources, proposed(held)),
                     (Decimal("1107000.00"), {"salary": "1107000.00"}, {"salary": "soe.txt, Net emoluments 1,107,000.00"}, {}))

  def test_confirming_a_figure_that_was_not_proposed_is_refused(self):
    with self.assertRaisesRegex(ValueError, "the case has no proposed figure for salary"): confirm(made(), T, "salary")

  def test_a_confirmed_figure_read_again_as_another_amount_is_proposed_and_listed_as_changed(self):
    held = confirm(made(paid("500.00", "business")), T, "business.gross_income")
    held = noted(held, "two.txt", Document("bank statement", "p", "z"), [("x", paid("300.00", "business", doc="two.txt"))], [], [])
    said = "bank.txt, 1 of the type business, two.txt, 1 of the type business"
    self.assertEqual(case(held, T)["changed"], {"business.gross_income": {"was": "500.00", "source": said}})

  def test_a_confirmed_figure_no_longer_read_is_proposed_at_zero(self):
    held = removed(confirm(made(read=(SALARY,)), T, "salary"), T, "soe.txt")
    self.assertEqual(proposals(held, T), ({"salary": Decimal(0)}, {"salary": "no document gives this figure at this time"}))

  def test_business_income_is_proposed_and_confirmed_inside_the_business(self):
    held = confirm(made(paid("500.00", "business")), T, "business.gross_income")
    self.assertEqual(held.given["business"], {"gross_income": Decimal("500.00")})
    self.assertEqual(held.sources["business.gross_income"], "bank.txt, 1 of the type business")

  def test_income_tax_paid_early_in_the_year_counts_for_the_year_before(self):
    rows = (paid("500.00", "tax_paid", date=f"15/{m[5:]}/{m[:4]}", way="out", month=m) for m in ("2025-07", "2025-10", "2025-11"))
    held = with_year(made(*rows), "2025-07")
    q = next(q for q in questions(held, T, proposed(held)) if q.subject == "bank.txt, paid out as tax paid")
    data = case(held, T)["earlier"]
    self.assertEqual((len(q.paid), sorted(data["payments"])), (1, sorted(k for k, p in held.payments.items() if p.month != "2025-11")))
    self.assertEqual([s["url"][-7:] for s in data["sources"]], ["#page=3", "#page=9"])
    self.assertIn("money paid out for the previous year", "\n".join(keep(held, T)))

  def early_and_late(self) -> Case:
    rows = (paid("500.00", "pension", date=f"15/{m[5:]}/{m[:4]}", way="out", month=m) for m in ("2025-08", "2025-11"))
    held = with_year(made(*rows), "2025-07")
    early, late = held.payments
    return answered(answered(held, T, early, "tax_paid"), T, late, "tax_paid")

  def test_only_tax_paid_early_can_be_counted_for_this_year(self):
    held = self.early_and_late()
    early, late = held.payments
    self.assertEqual(list(case(held, T)["earlier"]["asks"]), [early])
    with self.assertRaises(ValueError): subject_of(held, T, f"{late}, for this income year")

  def test_an_early_tax_payment_counted_for_this_year_keeps_its_label(self):
    held = self.early_and_late()
    early = next(iter(held.payments))
    held = answered(held, T, f"{early}, for this income year", "yes")
    data = case(held, T)["earlier"]
    self.assertEqual((data["payments"], data["kept"]), ({}, {early: f"{early}, for this income year"}))
    self.assertEqual(label_of(held, T, early, held.payments[early]), "tax_paid")
    self.assertEqual(proposed(answered(held, T, "bank.txt, paid out as tax paid", "yes")), {"quarterly_tax_paid": Decimal("1000.00")})
    self.assertIn(f"  {early}\n      tax_paid, from your answer, for this income year from your answer", "\n".join(keep(held, T)))

  def test_a_payment_no_longer_of_a_tax_type_is_not_kept_for_this_year(self):
    held = self.early_and_late()
    early = next(iter(held.payments))
    held = answered(answered(held, T, f"{early}, for this income year", "yes"), T, early, "pension")
    self.assertEqual(case(held, T)["earlier"]["kept"], {})

  def test_removing_the_statement_drops_the_answer_for_this_year(self):
    held = self.early_and_late()
    held = answered(held, T, f"{next(iter(held.payments))}, for this income year", "yes")
    self.assertEqual(removed(held, T, "bank.txt").decisions, {})

  def test_income_tax_paid_is_picked_without_a_business(self):
    held = made(paid("9000.00", "tax_paid", date="15/12/2025", way="out", month="2025-12"),
                paid("4000.00", "tax_paid", date="15/01/2026", way="out", month="2026-01"))
    subject = "bank.txt, paid out as tax paid"
    self.assertIn(subject, [q.subject for q in questions(held, T, proposed(held))])
    self.assertEqual(proposed(answered(held, T, subject, "payments 1")), {"quarterly_tax_paid": Decimal("9000.00")})

  def test_bank_charges_are_asked_only_of_a_business(self):
    subject = "bank.txt, paid out as bank charges"
    for income, asked in ((), False), ((paid("900.00", "business"),), True):
      held = made(*income, paid("75.00", "bank_charges", way="out"))
      with self.subTest(asked=asked): self.assertEqual(subject in [q.subject for q in questions(held, T, proposed(held))], asked)
    held = made(paid("900.00", "business"), paid("75.00", "bank_charges", way="out"))
    self.assertEqual(proposed(answered(held, T, subject, "yes"))["business.bank_charges"], Decimal("75.00"))

  def test_a_refund_of_a_business_cost_is_business_income(self):
    subject = "bank.txt, paid in as refund"
    alone = made(paid("40.00", "refund"))
    self.assertEqual(questions(alone, T, proposed(alone)), [])
    held = made(paid("900.00", "business"), paid("40.00", "refund"))
    self.assertIn(subject, [q.subject for q in questions(held, T, proposed(held))])
    self.assertEqual(proposed(answered(held, T, subject, "yes"))["business.other_income"], Decimal("40.00"))

  def test_months_no_statement_covers_are_asked_about_once_the_year_is_set(self):
    def gaps(held:Case) -> list[Asked]: return [q for q in questions(held, T, proposed(held)) if q.subject.startswith("months no statement")]
    first = (paid("5.00", "business", month="2025-07"), paid("5.00", "business", month="2025-09"))
    later = [(f"x{n}", paid("5.00", "business", month=m, doc="two.txt")) for n, m in enumerate(("2025-12", "2026-06"))]
    held = noted(made(*first, year=yearly("2025-07")), "two.txt", Document("bank statement", "q", "z"), later, [], [])
    self.assertEqual([q.about for q in gaps(held)], ["no statement covers 2025-10, 2025-11"])
    sent = next(q for q in case(held, T)["questions"] if q["subject"] == gaps(held)[0].subject)
    self.assertEqual(sent["months"], ["2025-10", "2025-11"])
    self.assertEqual(gaps(made(*first)), [])
    q = gaps(held)[0]
    self.assertEqual(said_to(answered(held, T, q.subject, "none"), q), "none")

  def alike(self, *more:Payment) -> Case: return made(paid("700.00", "cash", date="15/07/2025"), paid("300.00", "cash", date="20/07/2025"), *more)

  def test_credits_worded_alike_take_one_answer(self):
    held = self.alike()
    self.assertEqual([q.subject for q in questions(held, T, proposed(held))], ["payments paid in worded like CLIENT"])
    self.assertEqual(proposed(answered(held, T, "payments paid in worded like CLIENT", "business")), {"business.gross_income": Decimal("1000.00")})

  def test_an_alike_answer_moves_only_the_payments_it_listed(self):
    held = answered(self.alike(paid("5000.00", "business", date="25/07/2025")), T, "payments paid in worded like CLIENT", "other")
    self.assertEqual(proposed(held), {"business.gross_income": Decimal("5000.00")})
    later = noted(held, "two.txt", Document("bank statement", "q", "z"), [("x", paid("50.00", "cash", doc="two.txt"))], [], [])
    self.assertIn("two.txt, x", [q.subject for q in questions(later, T, proposed(later)) if said_to(later, q) is None])

  def test_an_alike_question_is_priced_by_all_its_payments(self):
    held = self.alike(paid("1200000.00", "business", date="25/07/2025"))
    q = next(q for q in questions(held, T, proposed(held)) if q.subject == "payments paid in worded like CLIENT")
    both = replace(held, decisions=decided(q, "business"))
    moved = balance(projected(both, derived(both, T))).amt - balance(projected(held, derived(held, T))).amt
    self.assertGreater(moved, 0)
    self.assertEqual(priced(held, T, q, based(held, T))["business"].amt, moved)

  def test_an_alike_question_lists_its_payments_in_the_case_data(self):
    asked = case(self.alike(), T)["questions"]
    self.assertEqual([(q["listed"], q["share"], len(q["payments"])) for q in asked], [(True, False, 2)])

  def test_a_remembered_answer_labels_a_later_payment_worded_alike(self):
    one = "bank.txt, 700.00 paid in on 15/07/2025, CLIENT"
    held = remember(answered(made(paid("700.00", "cash")), T, one, "business"), one)
    later = noted(held, "two.txt", Document("bank statement", "q", "z"), [("x", paid("50.00", "cash", doc="two.txt"))], [], [])
    waiting = [q for q in questions(later, T, proposed(later)) if said_to(later, q) is None]
    self.assertEqual((proposed(later), waiting), ({"business.gross_income": Decimal("750.00")}, []))
    self.assertEqual(case(later, T)["payments"]["two.txt, x"]["rule"], "payments paid in worded like CLIENT")

  def test_a_payment_with_its_own_answer_is_not_moved_by_a_remembered_one(self):
    one = "bank.txt, 700.00 paid in on 15/07/2025, CLIENT"
    held = remember(answered(self.alike(), T, one, "business"), one)
    held = answered(held, T, "bank.txt, 300.00 paid in on 20/07/2025, CLIENT", "other")
    self.assertEqual(proposed(held), {"business.gross_income": Decimal("700.00")})

  def test_forgetting_a_remembered_answer_asks_again(self):
    one = "bank.txt, 700.00 paid in on 15/07/2025, CLIENT"
    held = remember(answered(made(paid("700.00", "cash")), T, one, "business"), one)
    later = noted(held, "two.txt", Document("bank statement", "q", "z"), [("x", paid("50.00", "cash", doc="two.txt"))], [], [])
    self.assertIn("two.txt, x", [q.subject for q in questions(forgot(later, T, "payments paid in worded like CLIENT"), T, proposed(later))])

  def test_the_case_data_names_each_payments_wording_group(self):
    data = case(made(paid("700.00", "cash"), replace(paid("5.00", "cash"), description="12345")), T)["payments"]
    self.assertEqual(sorted((one["description"], one["alike"]) for one in data.values()),
                     [("12345", None), ("CLIENT", "payments paid in worded like CLIENT")])

  def test_only_an_answered_payment_with_wording_is_remembered(self):
    one, digits = "bank.txt, 700.00 paid in on 15/07/2025, CLIENT", replace(paid("5.00", "cash"), description="12345")
    for held, key, says in ((made(paid("700.00", "cash")), one, "CLIENT first, then keep the answer"),
                            (replace(made(paid("700.00", "cash")), decisions={one: SAME}), one, "CLIENT first, then keep the answer"),
                            (replace(made(digits), decisions={"k": "other"}, payments={"k": digits}), "k", "k has no words that identify the payee")):
      with self.subTest(says=says), self.assertRaisesRegex(ValueError, says): remember(held, key)

  def test_a_remembered_label_says_why_in_the_record(self):
    one = "bank.txt, 700.00 paid in on 15/07/2025, CLIENT"
    held = remember(answered(made(paid("700.00", "cash")), T, one, "business"), one)
    later = noted(held, "two.txt", Document("bank statement", "q", "z"), [("x", paid("50.00", "cash", doc="two.txt"))], [], [])
    self.assertIn("      business, from your answer for payments paid in worded like CLIENT", keep(later, T))

  def test_alike_credits_can_be_asked_about_one_by_one(self):
    held = answered(self.alike(), T, "payments paid in worded like CLIENT", EACH)
    self.assertEqual(len([q for q in questions(held, T, proposed(held)) if q.subject in held.payments]), 2)

  def test_account_numbers_keep_payers_apart(self):
    one, two = (replace(paid("5.00", "cash"), description=f"IB TRANSFER FROM {n} REF A1B2") for n in ("00123456", "00987654"))
    self.assertNotEqual(payer(one), payer(two))

  def two(self, held:Case, *paid_:Payment) -> Case:
    moved = [(f"x{n}", replace(x, document="two.txt")) for n, x in enumerate(paid_)]
    return noted(held, "two.txt", Document("bank statement", "q", "z"), moved, [], [])

  def test_a_relief_answer_carries_to_the_same_payee_in_a_later_statement(self):
    for said, want in (("yes", {"pension_contributions": Decimal("300.00")}), ("no", {})):
      held = answered(made(paid("100.00", "pension", way="out")), T, "bank.txt, paid out as pension", said)
      later = self.two(held, paid("200.00", "pension", date="15/08/2025", way="out", month="2025-08"))
      asked = case(later, T)["questions"]
      with self.subTest(said):
        self.assertEqual(proposed(later), want)
        self.assertEqual([(q["subject"], q["said"], q["carried"]) for q in asked], [("bank.txt, paid out as pension", said, False),
                                                                                  ("two.txt, paid out as pension", said, True)])

  def test_a_carried_answer_can_be_changed_for_its_own_statement(self):
    held = answered(made(paid("100.00", "pension", way="out")), T, "bank.txt, paid out as pension", "yes")
    later = answered(self.two(held, paid("200.00", "pension", way="out")), T, "two.txt, paid out as pension", "no")
    self.assertEqual(proposed(later), {"pension_contributions": Decimal("100.00")})

  def test_a_new_payee_keeps_the_later_question_open(self):
    held = answered(made(paid("100.00", "pension", way="out")), T, "bank.txt, paid out as pension", "yes")
    later = self.two(held, paid("200.00", "pension", way="out"), replace(paid("50.00", "pension", way="out"), description="ANOTHER PLAN"))
    self.assertEqual([q.subject for q in questions(later, T, proposed(later)) if said_to(later, q) is None], ["two.txt, paid out as pension"])

  def test_a_later_answer_replaces_what_a_payee_carries(self):
    office = replace(paid("100.00", "business_expense", way="out"), description="OFFICE")
    held = made(paid("900.00", "business"), office, replace(office, amount=Decimal("40.00"), date="16/07/2025"))
    for said, want in (("payments 1", None), ("50.00", "25.00")):
      done = answered(answered(held, T, "bank.txt, paid out as business expense", "yes"), T, "bank.txt, paid out as business expense", said)
      later = self.two(done, replace(office, amount=Decimal("70.00")))
      q = next(q for q in questions(later, T, proposed(later)) if q.subject == "two.txt, paid out as business expense")
      with self.subTest(said): self.assertEqual(said_to(later, q), want)

  def test_forgetting_an_answer_withdraws_what_it_carried(self):
    held = forgot(answered(made(paid("100.00", "pension", way="out")), T, "bank.txt, paid out as pension", "yes"), T, "bank.txt, paid out as pension")
    self.assertEqual((proposed(held), [q.subject for q in questions(held, T, proposed(held)) if said_to(held, q) is None]),
                     ({}, ["bank.txt, paid out as pension"]))

  def test_a_carried_pick_counts_the_payees_said_yes(self):
    office, shop = (replace(paid(a, "business_expense", way="out"), description=d) for a, d in (("100.00", "OFFICE"), ("40.00", "SHOP")))
    held = made(paid("900.00", "business"), office, replace(shop, date="16/07/2025"))
    held = answered(held, T, "bank.txt, paid out as business expense", "payments 1")
    later = self.two(held, replace(office, amount=Decimal("70.00")), replace(shop, amount=Decimal("30.00")))
    self.assertEqual(proposed(later)["business.other_expenses"], Decimal("170.00"))

  def test_a_stored_answer_that_no_longer_fits_is_never_replaced_by_a_carried_one(self):
    office = replace(paid("100.00", "business_expense", way="out"), description="OFFICE")
    held = answered(made(paid("900.00", "business"), office), T, "bank.txt, paid out as business expense", "yes")
    later = answered(self.two(held, replace(office, amount=Decimal("70.00"))), T, "two.txt, paid out as business expense", "60.00")
    shrunk = replace(later, payments={k: replace(p, amount=Decimal("50.00")) if k == "two.txt, x0" else p for k, p in later.payments.items()})
    q = next(q for q in questions(shrunk, T, proposed(shrunk)) if q.subject == "two.txt, paid out as business expense")
    self.assertIsNone(said_to(shrunk, q))

  def test_a_pick_is_kept_as_the_payments_it_names(self):
    held = made(paid("900.00", "business"), paid("100.00", "tax_paid", date="15/12/2025", way="out", month="2025-12"),
                paid("40.00", "tax_paid", date="16/12/2025", way="out", month="2025-12"))
    held = answered(held, T, "bank.txt, paid out as tax paid", "payments 2, 1")
    self.assertEqual((held.decisions["bank.txt, paid out as tax paid"], proposed(held)["quarterly_tax_paid"]), ("payments 1, 2", Decimal("140.00")))

  def test_a_typed_share_carries_to_the_same_payee_in_a_later_statement(self):
    for part, later, want in (("40.00", "50.00", "20.00"), ("33.33", "10.00", "3.33")):
      held = answered(made(paid("900.00", "business"), paid("100.00", "bills", way="out")), T, "bank.txt, paid out as bills", part)
      after = self.two(held, paid(later, "bills", way="out"))
      q = next(q for q in questions(after, T, proposed(after)) if q.subject == "two.txt, paid out as bills")
      with self.subTest(part): self.assertEqual((said_to(after, q), proposed(after)["business.utilities"]), (want, Decimal(part) + Decimal(want)))

  def test_a_typed_part_over_several_payees_carries_nothing(self):
    elec, water = (replace(paid("100.00", "bills", way="out"), description=d) for d in ("ELEC", "WATER"))
    held = answered(made(paid("900.00", "business"), elec, replace(water, date="16/07/2025")), T, "bank.txt, paid out as bills", "100.00")
    after = self.two(held, replace(elec, amount=Decimal("80.00")))
    q = next(q for q in questions(after, T, proposed(after)) if q.subject == "two.txt, paid out as bills")
    self.assertIsNone(said_to(after, q))

  def test_a_carried_figure_names_the_payees_it_came_from(self):
    held = answered(made(paid("100.00", "pension", way="out")), T, "bank.txt, paid out as pension", "yes")
    later = self.two(held, paid("200.00", "pension", way="out"))
    self.assertIn("your answer for payments paid out worded like CLIENT, as pension", proposals(later, T)[1]["pension_contributions"])

  def test_the_payments_and_readings_behind_a_figure_add_up_to_it(self):
    pension, other = paid("90.00", "pension", way="out"), replace(paid("40.00", "pension", way="out"), description="OTHER PLAN")
    line = Line("form.txt", Decimal("1.00"), "X", "which line", (("net_emoluments", "pay"),))
    fed = made(paid("500.00", "business"), paid("70.00", "business", check="does not agree"), paid("9.00", "business", month="2023-07"))
    cases = {"fed": fed,
             "read": made(read=(SALARY,)),
             "picked": answered(made(paid("100.00", "tax_paid", date="15/12/2025", way="out", month="2025-12"),
                                     paid("40.00", "tax_paid", date="16/12/2025", way="out", month="2025-12")), T,
                                "bank.txt, paid out as tax paid", "payments 2"),
             "carried": self.two(answered(made(pension, other), T, "bank.txt, paid out as pension", "yes"), pension),
             "form line": answered(noted(made(), "form.txt", Document("statement of emoluments", "p", "c"), [], [], [("1.00 on the line X", line)]),
                                    T, "form.txt, 1.00 on the line X", "net_emoluments"),
             "left out": answered(made(paid("500.00", "business"), paid("30.00", "business", date="16/07/2025")), T,
                                  "bank.txt, 30.00 paid in on 16/07/2025, CLIENT", OUT)}
    for name, held in cases.items():
      found = {**{k: p.amount for k, p in held.payments.items()}, **{k: r.amount for k, r in held.readings.items()},
               **{k: one.amount for k, one in held.lines.items()}}
      with self.subTest(name):
        got = {fact: sum((found[k] for k in keys), Decimal("0.00")) for fact, keys in case(held, T)["evidence"].items()}
        self.assertTrue(got)
        self.assertEqual(got, {fact: amt for fact, (amt, _) in derived(held, T).items()})

  def test_a_typed_part_names_its_question_as_the_source(self):
    held = answered(made(paid("900.00", "business"), paid("100.00", "bills", way="out")), T, "bank.txt, paid out as bills", "40.00")
    self.assertEqual(case(held, T)["evidence"]["business.utilities"], ["bank.txt, paid out as bills"])

  def test_a_figure_entered_by_hand_names_no_payments(self):
    held = set_fact(made(paid("500.00", "business")), T, "business.gross_income", "800")
    self.assertNotIn("business.gross_income", case(held, T)["evidence"])

  def test_bank_interest_is_proposed_as_exempt_interest(self):
    self.assertEqual(proposed(made(paid("12.50", "interest"), paid("7.50", "interest"))), {"exempt_interest": Decimal("20.00")})

  def test_a_payment_whose_balance_does_not_agree_is_not_counted_until_vouched_for(self):
    held = made(paid("500.00", "business", check="does not agree"), paid("300.00", "business", date="16/07/2025"))
    self.assertEqual(proposed(held), {"business.gross_income": Decimal("300.00")})
    vouched = replace(held, decisions={"bank.txt, 500.00 paid in on 15/07/2025, CLIENT": "business"})
    self.assertEqual(proposed(vouched), {"business.gross_income": Decimal("800.00")})

  def test_payments_whose_balance_was_not_checked_are_counted_and_named(self):
    held = made(paid("500.00", "business", check="not checked"), paid("300.00", "business", date="16/07/2025"))
    self.assertEqual(proposals(held, T)[1], {"business.gross_income": "bank.txt, 2 of the type business, 1 with no balance check"})

  def test_every_question_carries_a_plain_headline(self):
    held = made(paid("900.00", "rent", check="does not agree"), paid("500.00", "pay"), paid("40.00", "business_expense", way="out"),
                paid("60.00", "pension", way="out"))
    self.assertEqual([q.headline for q in questions(held, T, proposed(held))],
                     ["the totals do not include a payment", "add your statement of emoluments", "business costs, but no business income?",
                      "did these payments go into your approved pension scheme?"])

  def test_a_kind_given_to_an_unclear_payment_counts(self):
    held = replace(made(paid("700.00", "cash")), decisions={"bank.txt, 700.00 paid in on 15/07/2025, CLIENT": "rent"})
    self.assertEqual(proposed(held), {"rent": Decimal("700.00")})

  def test_an_answer_that_no_longer_fits_its_question_counts_nothing_and_reopens_it(self):
    held = replace(made(paid("40.00", "business_expense", way="out"), business={"gross_income": 1000}),
                   decisions={"bank.txt, paid out as business expense": "90"})
    data = case(held, T)["questions"][0]
    self.assertEqual((proposed(held), data["said"], data["earlier"]), ({}, None, "90"))

  def test_the_case_comes_back_as_data_with_every_number_as_text(self):
    got = case(made(paid("500.00", "business"), read=(SALARY,), salary=1000), T)
    self.assertEqual((got["facts"]["salary"], got["proposed"], list(got["documents"])),
                     ("1000", {"business.gross_income": "500.00", "salary": "1107000.00"}, ["bank.txt", "soe.txt"]))
    self.assertEqual(got["readings"]["soe.txt, salary"], {"document": "soe.txt", "fact": "salary", "amount": "1107000.00",
                                                          "quote": "Net emoluments 1,107,000.00", "wrong": False})
    self.assertEqual(got["figures"][0]["sources"][0]["url"], "https://www.mra.mu/download/ITAConsolidated.pdf#page=13")

  def test_money_in_is_summed_by_kind_with_the_largest_first(self):
    got = received(made(paid("12.50", "interest"), paid("500.00", "business", date="16/07/2025"), paid("100.00", "business", date="17/07/2025")), T)
    self.assertEqual(got["kinds"], {"business": Decimal("600.00"), "interest": Decimal("12.50")})

  def test_money_in_is_summed_by_what_it_counts_as(self):
    got = received(made(paid("12.50", "interest"), paid("500.00", "business", date="16/07/2025"), paid("7.00", "cash", date="17/07/2025"),
                        paid("3.00", "other", date="18/07/2025")), T)
    self.assertEqual(got["groups"], {"income": Decimal("500.00"), "exempt": Decimal("12.50"), "unsorted": Decimal("7.00"), "other": Decimal("3.00")})

  def test_a_group_with_nothing_shows_zero_to_the_cent(self):
    self.assertEqual(str(received(made(paid("5.00", "business")), T)["groups"]["exempt"]), "0.00")

  def test_each_month_holds_its_total_its_groups_and_its_payments(self):
    got = received(made(paid("500.00", "business"), paid("12.50", "interest", date="16/07/2025")), T)["months"]["2025-07"]
    self.assertEqual(got, {"total": Decimal("512.50"), "groups": {"income": Decimal("500.00"), "exempt": Decimal("12.50")},
                           "payments": {"income": ["bank.txt, 500.00 paid in on 15/07/2025, CLIENT"],
                                        "exempt": ["bank.txt, 12.50 paid in on 16/07/2025, CLIENT"]}})

  def test_the_income_year_runs_from_july_to_the_june_after_the_latest_payment(self):
    self.assertEqual(months_of(made(paid("5.00", "business", month="2026-03"))), year_of("2025-07"))

  def test_the_case_year_holds_the_months_whatever_the_latest_payment(self):
    self.assertEqual(months_of(made(paid("5.00", "business", month="2027-03"), year=yearly("2025-07")))[0], "2025-07")

  def test_payments_outside_the_year_or_without_a_month_are_named(self):
    held = made(paid("5.00", "business", month="2024-03"), paid("6.00", "business", date="16/07/2025", month=None), year=yearly("2025-07"))
    got = received(held, T)
    self.assertEqual((got["outside"], got["undated"], got["groups"]["income"]),
                     (["bank.txt, 5.00 paid in on 15/07/2025, CLIENT"], ["bank.txt, 6.00 paid in on 16/07/2025, CLIENT"], Decimal("6.00")))

  def test_a_payment_left_out_by_the_person_is_counted_nowhere(self):
    held = replace(made(paid("5.00", "business")), decisions={"bank.txt, 5.00 paid in on 15/07/2025, CLIENT": OUT})
    self.assertEqual((received(held, T)["kinds"], proposed(held)), ({}, {}))

  def test_an_amount_a_count_and_a_yes_or_no_are_entered_with_their_source(self):
    held = set_fact(set_fact(set_fact(made(), T, "salary", "1,200.50"), T, "dependants", "2"), T, "spouse_above_interest_bar", "yes")
    self.assertEqual((held.given["salary"], held.given["dependants"], held.given["spouse_above_interest_bar"], held.sources["salary"]),
                     (Decimal("1200.50"), 2, True, ENTERED))

  def test_a_business_line_is_entered_inside_the_business(self):
    self.assertEqual(set_fact(made(), T, "business.gross_income", "900").given["business"], {"gross_income": Decimal("900")})

  def test_an_entered_figure_replaces_its_proposal_until_a_document_reads_it_differently(self):
    held = set_fact(made(read=(SALARY,)), T, "salary", "1000000")
    self.assertEqual((proposed(held), held.confirmed), ({}, {"salary": "1107000.00"}))
    again = noted(held, "two.txt", Document("statement of emoluments", "p", "z"), [], [replace(SALARY, document="two.txt", amount=Decimal(1))], [])
    self.assertEqual(proposed(again), {"salary": Decimal("1107001.00")})

  def test_a_cleared_fact_is_gone_with_its_source(self):
    held = set_fact(set_fact(made(), T, "salary", "1000"), T, "salary", " ")
    self.assertEqual(("salary" in held.given, held.sources), (False, {}))

  def test_an_unknown_fact_or_value_is_refused(self):
    for name, said, says in (("luck", "1", "cannot type a figure for luck"), ("dependants", "two", "no decimal part, not two"),
                             ("resident", "maybe", "yes or no"), ("salary", "lots", "not an amount")):
      with self.subTest(name), self.assertRaisesRegex(ValueError, says): set_fact(made(), T, name, said)

  def test_a_confirmed_figure_goes_back_to_waiting(self):
    held = unconfirmed(confirm(made(read=(SALARY,)), T, "salary"), "salary")
    self.assertEqual(("salary" in held.given, held.confirmed, proposed(held)), (False, {}, {"salary": Decimal("1107000.00")}))

  def test_a_figure_never_confirmed_or_entered_by_hand_cannot_go_back(self):
    for held in (made(salary=1), set_fact(made(), T, "salary", "1")):
      with self.subTest(held.sources), self.assertRaisesRegex(ValueError, "not a proposed figure that you accepted"): unconfirmed(held, "salary")

  def test_costs_said_not_to_be_a_business_count_nothing_whatever_was_answered_before(self):
    key = "bank.txt, 500,000.00 paid in on 15/07/2025, CLIENT"
    held = made(paid("500000.00", "business"), paid("40000.00", "business_expense", way="out"))
    held = replace(held, decisions={"bank.txt, paid out as business expense": "yes", key: "other", "bank.txt, business costs": "not"})
    self.assertEqual(proposed(held), {})

  def test_an_answer_about_pay_goes_with_the_last_document_that_held_pay(self):
    held = removed(replace(made(paid("900.00", "pay")), decisions={"money labelled pay": "business"}), T, "bank.txt")
    self.assertEqual(held.decisions, {})

  def test_a_label_the_tables_do_not_list_is_refused_by_name(self):
    with self.assertRaisesRegex(ValueError, r"bank\.txt has a payment of the type windfall, and the tables of types do not have this type"):
      keep(made(paid("5.00", "windfall")), T)

  def test_an_answer_about_a_payment_that_names_no_kind_counts_nothing(self):
    held = replace(made(paid("5.00", "business")), decisions={"bank.txt, 5.00 paid in on 15/07/2025, CLIENT": "windfall"})
    self.assertEqual(proposed(held), {"business.gross_income": Decimal("5.00")})

  def test_a_certificate_question_closes_once_its_figure_is_entered(self):
    for kind, fact, said in (("housing_loan", "housing_loan_interest", "25,000"), ("medical_insurance", "medical_insurance", "15,000 8000"),
                             ("school_fees", "school_fees", "40000")):
      held = made(paid("100.00", kind, way="out"), dependants=2)
      with self.subTest(kind):
        self.assertEqual([q["closes"] for q in case(held, T)["questions"]], [fact])
        self.assertEqual(questions(set_fact(held, T, fact, said), T, proposed(held)), [])

  def test_a_list_of_amounts_is_entered_in_order_and_cleared_when_blank(self):
    held = set_fact(made(dependants=1), T, "medical_insurance", "15,000; 8000")
    self.assertEqual((held.given["medical_insurance"], held.sources["medical_insurance"]), ([Decimal("15000"), Decimal("8000")], ENTERED))
    self.assertNotIn("medical_insurance", set_fact(held, T, "medical_insurance", " ").given)
    with self.assertRaisesRegex(ValueError, "not an amount lots"): set_fact(held, T, "school_fees", "lots")

  def test_forgetting_needs_something_said(self):
    with self.assertRaisesRegex(ValueError, "the case has no answer for x"): forgot(made(), T, "x")

  def test_a_removed_document_takes_its_records_and_leaves_the_others(self):
    key = "bank.txt, 500.00 paid in on 15/07/2025, CLIENT"
    held = replace(made(paid("500.00", "business"), read=(SALARY,)), decisions={"soe.txt, salary": "wrong", key: "rent"})
    held = removed(held, T, "soe.txt")
    self.assertEqual((list(held.documents), held.readings, list(held.decisions), proposed(held)),
                     (["bank.txt"], {}, ["bank.txt, 500.00 paid in on 15/07/2025, CLIENT"], {"rent": Decimal("500.00")}))

  def test_a_document_the_case_does_not_hold_cannot_be_removed(self):
    with self.assertRaisesRegex(ValueError, r"the case has no document x\.txt"): removed(made(), T, "x.txt")

  def test_a_case_is_given_twelve_months_from_july(self):
    self.assertEqual(with_year(made(), "2025-07").year, {"from": "2025-07", "to": "2026-06"})

  def test_a_year_starts_in_july(self):
    with self.assertRaisesRegex(ValueError, "an income year starts in month 7, not in '2025-01'"): with_year(made(), "2025-01")

  def test_a_question_is_priced_by_each_answer(self):
    held = made(paid("900000.00", "cash"))
    prices = case(held, T)["questions"][0]["prices"]
    self.assertEqual((prices["business"]["amount"], prices["other"]["amount"]), ("40000", "0"))

  def test_a_question_is_priced_with_the_money_in_every_other_document(self):
    two = [("x", paid("500000.00", "business", doc="two.txt"))]
    held = noted(made(paid("100000.00", "cash")), "two.txt", Document("bank statement", "p", "z"), two, [], [])
    self.assertEqual(case(held, T)["questions"][0]["prices"]["business"]["amount"], "10000")

  def test_every_price_matches_working_out_the_whole_case_again(self):
    held = made(paid("700000.00", "unclear"), paid("90000.00", "rent", date="16/07/2025", check="does not agree"),
                paid("400000.00", "business_expense", way="out"), paid("50000.00", "pension", way="out", date="17/07/2025"))
    held = noted(held, "two.txt", Document("bank statement", "p", "z"),
                 [("a", paid("2000000.00", "business", doc="two.txt")), ("b", paid("30000.00", "bills", way="out", doc="two.txt"))], [], [])
    for given in (held, removed(held, T, "two.txt")):
      before = balance(projected(given, derived(given, T)))
      for q in questions(given, T, proposed(given)):
        for choice, fig in priced(given, T, q, based(given, T)).items():
          chosen = replace(given, decisions=given.decisions | decided(q, choice))
          with self.subTest(q.subject, choice=choice):
            self.assertEqual(fig.amt, balance(projected(given, derived(chosen, T))).amt - before.amt)

  def test_a_cost_is_priced_with_the_income_held_in_another_document(self):
    held = noted(made(paid("400000.00", "business_expense", way="out")), "two.txt", Document("bank statement", "p", "z"),
                 [("a", paid("2000000.00", "business", doc="two.txt"))], [], [])
    q = next(q for q in questions(held, T, proposed(held)) if q.subject == "bank.txt, paid out as business expense")
    self.assertLess(priced(held, T, q, based(held, T))["yes"].amt, 0)

  def test_a_question_whose_answers_change_nothing_carries_no_price(self):
    held = made(paid("100.00", "medical_insurance", way="out"), salary=1200000)
    self.assertEqual(case(held, T)["questions"][0]["prices"], {})

  def statements(self, *two:Payment) -> Case:
    held = made(paid("500.00", "business"), paid("90.00", "pension", way="out"))
    return noted(held, "two.txt", Document("bank statement", "p", "z"), [(f"x{n}", p) for n, p in enumerate(two)], [], [])

  def test_a_payment_read_in_two_statements_is_counted_once_and_asked_about(self):
    held = self.statements(paid("500.00", "business", doc="two.txt"))
    q = next(q for q in questions(held, T, proposed(held)) if q.document == "two.txt")
    self.assertEqual(proposed(held), {"business.gross_income": Decimal("500.00")})
    self.assertEqual((q.headline, q.choices[0][0]), ("a payment is in two statements", SAME))
    for said, amt in (("business", "1000.00"), (SAME, "500.00"), (OUT, "500.00")):
      with self.subTest(said):
        self.assertEqual(proposed(replace(held, decisions={"two.txt, x0": said}))["business.gross_income"], Decimal(amt))

  def test_a_payment_the_first_statement_holds_once_counts_again_the_second_time(self):
    held = self.statements(paid("500.00", "business", doc="two.txt"), paid("500.00", "business", doc="two.txt"))
    self.assertEqual(proposed(held), {"business.gross_income": Decimal("1000.00")})

  def test_leaving_out_the_first_copy_counts_the_second(self):
    held = replace(self.statements(paid("500.00", "business", doc="two.txt")), decisions={"bank.txt, 500.00 paid in on 15/07/2025, CLIENT": OUT})
    self.assertEqual((proposed(held), [q.subject for q in questions(held, T, proposed(held)) if q.headline == "a payment is in two statements"]),
                     ({"business.gross_income": Decimal("500.00")}, []))

  def test_a_payment_said_to_be_the_same_counts_again_once_the_first_statement_goes(self):
    held = removed(replace(self.statements(paid("500.00", "business", doc="two.txt")), decisions={"two.txt, x0": SAME}), T, "bank.txt")
    self.assertEqual(proposed(held), {"business.gross_income": Decimal("500.00")})

  def test_a_first_copy_that_counts_nothing_leaves_the_second_counted(self):
    for first in (paid("500.00", "business", check="does not agree"), paid("500.00", "business", month="2023-07")):
      two = [("x", paid("500.00", "business", doc="two.txt"))]
      held = noted(made(first, year=yearly("2025-07")), "two.txt", Document("bank statement", "p", "z"), two, [], [])
      with self.subTest(first.check, month=first.month):
        asked = [q.headline for q in questions(held, T, proposed(held)) if not q.subject.startswith("months no statement")]
        self.assertEqual((proposed(held), asked),
                         ({"business.gross_income": Decimal("500.00")}, ["the totals do not include a payment"] if first.check != "ok" else []))

  def test_a_copy_is_left_out_of_the_money_paid_in(self):
    self.assertEqual(received(self.statements(paid("500.00", "business", doc="two.txt")), T)["kinds"], {"business": Decimal("500.00")})

  def test_every_price_matches_the_whole_case_when_statements_overlap(self):
    held = self.statements(paid("500.00", "business", doc="two.txt"), paid("90.00", "pension", way="out", doc="two.txt"),
                           paid("700000.00", "business", doc="two.txt", date="18/07/2025"))
    held = replace(held, decisions={"two.txt, paid out as pension": "yes", "bank.txt, paid out as pension": "yes"})
    before = balance(projected(held, derived(held, T)))
    for q in questions(held, T, proposed(held)):
      for choice, fig in priced(held, T, q, based(held, T)).items():
        chosen = replace(held, decisions=held.decisions | decided(q, choice))
        with self.subTest(q.subject, choice=choice): self.assertEqual(fig.amt, balance(projected(held, derived(chosen, T))).amt - before.amt)

  def test_a_question_waiting_for_a_figure_carries_no_price(self):
    held = made(paid("900000.00", "pay"))
    q = next(q for q in case(held, T)["questions"] if q["subject"] == "money labelled pay")
    self.assertEqual((q["closes"], q["prices"]), ("salary", {}))

  def test_the_case_data_lists_every_payment_dated_outside_the_year(self):
    held = made(paid("5.00", "business", month="2024-03"), paid("6.00", "pension", way="out", month="2024-04"),
                paid("7.00", "business", month="2025-08"), year=yearly("2025-07"))
    self.assertEqual(case(held, T)["outside"], ["bank.txt, 5.00 paid in on 15/07/2025, CLIENT", "bank.txt, 6.00 paid out on 15/07/2025, CLIENT"])

  def test_a_value_reads_the_way_a_person_says_it(self):
    self.assertEqual([shown(v) for v in (True, False, "x", Decimal("1200.5"))], ["yes", "no", "x", "1,200.5"])

  def test_a_written_case_is_plain_json(self):
    kept = json.loads(written(made(paid("5.00", "business"))))["payments"]
    self.assertEqual(kept["bank.txt, 5.00 paid in on 15/07/2025, CLIENT"]["amount"], "5.00")

if __name__ == "__main__": unittest.main()
