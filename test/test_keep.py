import json, unittest
from decimal import Decimal
from it01.keep import (TITLES, VERSION, WORDING, Document, answer, apart, case, confirm, derived, dumped, figures, fingerprint, keep, loaded,
                       needing, newly, noted, priced, reanswered, received, relabelled, removed, set_fact, shown, with_year)
from it01.kinds import spoken
from it01.law import Source

STATEMENT = Document(name="bank.txt", path="in/bank.txt", mark="a", kind="bank statement")
FACTS = {"resident": True, "dependants": 1, "salary": 1107000, "paye_withheld": 71401,
         "sources": {"salary": "Total emoluments        1,107,000.00"},
         "answers": {"cash of 500.00 on 05/07/2025": "sold my old bicycle"},
         "version": VERSION, "documents": {"statement.txt": "statement of emoluments"},
         "labels": {"bank.txt, 12.50 paid in on 05/07/2025, INTEREST": "interest"},
         "paid": {"bank.txt, 40.00 paid out on 06/07/2025, STATIONERY": "business_expense"},
         "outside": {"bank.txt, 9.00 paid in on 30/06/2025, OLD": "paid in"},
         "currencies": {"bank.txt": "ABC"},
         "checks": {"statement.txt, 12.50 paid in on 05/07/2025, INTEREST": "not checked"},
         "read": {"statement.txt, salary": "1,107,000.00 read from Total emoluments        1,107,000.00",
                  "statement.txt, other_income": "40,000.00 read from Rent received 40,000.00"},
         "pending": {"cash of 1,200.00 on 12/08/2025": "where did this come from"}}

def written(**changes:object) -> str: return json.dumps(FACTS | changes)

class TestKeep(unittest.TestCase):
  def test_the_record_holds_every_heading(self):
    ret = "\n".join(keep(written()))
    for heading in ("facts you confirmed", "figures", *TITLES.values()): self.assertIn(heading, ret)

  def test_every_aside_part_is_shown_under_its_own_key(self):
    ret = keep(written())
    for key, value in (("statement.txt", "statement of emoluments"), ("cash of 1,200.00 on 12/08/2025", "where did this come from")):
      with self.subTest(key): self.assertEqual(ret[ret.index(f"  {key}") + 1], f"      {value}")

  def test_a_fact_is_shown_with_the_wording_it_came_from(self):
    ret = keep(written())
    at = next(i for i, line in enumerate(ret) if line.startswith("  salary"))
    self.assertEqual(ret[at + 1], "      Total emoluments        1,107,000.00")

  def test_a_figure_is_shown_with_the_law_behind_it(self):
    ret = "\n".join(keep(written()))
    self.assertIn("  income tax", ret)
    self.assertIn("https://www.mra.mu/download/ITAConsolidated.pdf#page=26", ret)

  def test_an_answer_is_shown_under_the_question(self):
    ret = keep(written())
    self.assertEqual(ret[ret.index("  cash of 500.00 on 05/07/2025") + 1], "      sold my old bicycle")

  def test_the_wording_never_reaches_the_computation(self):
    rich = FACTS | {"business": {"gross_income": 900000, "assets": [{"kind": "computer", "cost": 80000}]}}
    plain = {k: v for k, v in rich.items() if k not in WORDING}
    self.assertEqual(figures(plain), figures(apart(loaded(json.dumps(rich)))[0]))

  def test_an_asset_that_produced_a_figure_is_in_the_record(self):
    ret = keep(written(business={"gross_income": 900000, "assets": [{"kind": "computer", "cost": 80000}]}))
    self.assertTrue(any(line.strip().startswith("kind") and "computer" in line for line in ret))
    self.assertTrue(any(line.startswith("  annual allowance on computer") for line in ret))

  def test_the_same_key_written_twice_is_refused(self):
    twice = json.dumps(FACTS)[:-1] + ', "answers": {"cash": "a", "cash": "b"}}'
    with self.assertRaisesRegex(ValueError, "written twice"): keep(twice)

  def test_an_empty_source_is_refused(self):
    with self.assertRaisesRegex(ValueError, "nothing left blank"): keep(written(sources={"salary": "   "}))

  def test_a_source_on_a_fact_with_no_wording_slot_is_refused(self):
    with self.assertRaisesRegex(ValueError, "cannot name"):
      keep(written(business={"gross_income": 900000}, sources={"business": "the accounts"}))

  def test_a_fact_that_is_not_a_number_is_refused(self):
    with self.assertRaisesRegex(ValueError, "invalid salary"): keep(json.dumps(FACTS).replace("1107000", "NaN"))

  def test_a_blank_question_is_refused(self):
    with self.assertRaisesRegex(ValueError, "nothing left blank"): keep(written(answers={"": "an answer"}))

  def test_wording_written_as_null_is_refused(self):
    with self.assertRaisesRegex(ValueError, "object of text"): keep(written(sources=None))

  def test_a_bad_fact_is_refused_before_the_record_is_built(self):
    for bad, says in (({"salary": None}, "invalid salary"), ({"business": {"assets": [1]}}, "asset must be a JSON object")):
      with self.subTest(says):
        with self.assertRaisesRegex(ValueError, says): keep(json.dumps({"resident": True} | bad))

  def test_each_asset_is_listed_on_its_own(self):
    two = written(business={"assets": [{"kind": "computer", "cost": 8}, {"kind": "furniture", "cost": 9}]})
    ret = "\n".join(keep(two))
    self.assertEqual(ret.count("\n    assets"), 1)
    self.assertIn("\n      1\n", ret)
    self.assertIn("\n      2\n", ret)

  def test_a_source_or_a_confirmed_figure_naming_no_given_fact_is_refused(self):
    for part in ({"sources": {"not_a_fact": "somewhere"}}, {"confirmed": {"other_income": "40000.00"}}):
      with self.subTest(part), self.assertRaisesRegex(ValueError, "name facts the case does not give"): keep(written(**part))

  def test_wording_that_is_not_text_is_refused(self):
    for part in WORDING:
      with self.subTest(part):
        with self.assertRaisesRegex(ValueError, "object of text"): keep(written(**{part: {"salary": 1}}))

  def test_a_facts_file_with_no_wording_still_makes_a_record(self):
    plain = {k: v for k, v in FACTS.items() if k not in WORDING}
    ret = "\n".join(keep(json.dumps(plain)))
    self.assertIn("figures", ret)
    for title in TITLES.values(): self.assertNotIn(title, ret)

  def test_confirming_moves_a_figure_among_the_facts(self):
    text = confirm(written(), "other_income")
    raw = loaded(text)
    self.assertEqual((raw["other_income"], apart(raw)[2], raw["sources"]["salary"]),
                     (Decimal(40000), {}, "Total emoluments        1,107,000.00"))

  def test_confirming_records_the_value_confirmed(self):
    self.assertEqual(loaded(confirm(written(), "other_income"))["confirmed"], {"other_income": "40000.00"})

  def test_a_confirmed_figure_read_again_as_another_amount_is_proposed_and_listed_as_changed(self):
    raw = loaded(confirm(written(), "other_income"))
    raw["read"]["statement.txt, other_income"] = "45,000.00 read from Rent received 45,000.00"
    got = case(dumped(raw))
    self.assertEqual((got["proposed"], got["changed"], got["facts"]["other_income"]),
                     ({"other_income": "45000.00"}, {"other_income": {"was": "40000.00", "source": "statement.txt, Rent received 45,000.00"}},
                      "40000.00"))

  def test_a_confirmed_fact_keeps_its_source_after_its_reading_changes(self):
    raw = loaded(confirm(written(), "other_income"))
    raw["read"]["statement.txt, other_income"] = "45,000.00 read from Rent received 45,000.00"
    self.assertEqual(apart(raw)[1]["sources"]["other_income"], "statement.txt, Rent received 40,000.00")

  def test_a_confirmed_figure_no_longer_read_is_proposed_at_zero(self):
    raw = loaded(confirm(written(), "other_income"))
    del raw["read"]["statement.txt, other_income"]
    got = case(dumped(raw))
    gone = {"other_income": {"was": "40000.00", "source": "no longer read from any document"}}
    self.assertEqual((got["proposed"], got["changed"]), ({"other_income": "0"}, gone))

  def test_a_file_that_keeps_proposed_figures_is_refused(self):
    with self.assertRaisesRegex(ValueError, "kept by an earlier version"): keep(written(proposed={"other_income": 40000}))

  def test_a_file_with_documents_and_no_version_is_refused(self):
    unversioned = json.dumps({k: v for k, v in FACTS.items() if k != "version"})
    with self.assertRaisesRegex(ValueError, "a case of version none cannot be read"): keep(unversioned)

  def test_a_reading_that_names_no_document_or_no_fact_is_refused(self):
    for key in ("other.txt, salary", "statement.txt, not_a_fact"):
      with self.subTest(key), self.assertRaisesRegex(ValueError, "names a document or a fact the case does not know"):
        keep(written(read={key: "1.00 read from Total 1.00"}))

  def test_a_reading_that_is_not_an_amount_is_refused(self):
    for said in ("forty read from Rent", "40,000.00 from Rent", "-1 read from Rent", "1.555 read from Rent"):
      with self.subTest(said), self.assertRaisesRegex(ValueError, "not an amount"): keep(written(read={"statement.txt, rent": said}))

  def test_confirming_one_of_two_leaves_the_other_proposed(self):
    two = written(read=FACTS["read"] | {"statement.txt, other_reliefs": "5,000.00 read from Relief claimed 5,000.00"})
    self.assertEqual(apart(loaded(confirm(two, "other_income")))[2], {"other_reliefs": Decimal(5000)})

  def test_business_income_is_proposed_under_the_business(self):
    text, how = noted(written(), STATEMENT, [], labels=(("20,975.00 paid in on 05/07/2025, CLIENT", "business"),))
    self.assertEqual((tuple(newly(written(), text)), apart(loaded(text))[2]["business.gross_income"]), (("business.gross_income",), Decimal(20975)))

  def test_confirmed_business_income_joins_the_business_block(self):
    read = {"statement.txt, business.gross_income": "20,975.00 read from Sales 20,975.00"}
    for given, want in (({}, {"gross_income": 20975}), ({"business": {"wages": 5000}}, {"wages": 5000, "gross_income": 20975})):
      with self.subTest(given):
        raw = loaded(confirm(written(read=read, **given), "business.gross_income"))
        self.assertEqual((raw["business"], raw["sources"]["business.gross_income"]), (want, "statement.txt, Sales 20,975.00"))

  def test_the_record_shows_where_confirmed_business_income_came_from(self):
    name = "business.gross_income"
    lines = keep(confirm(written(read={f"statement.txt, {name}": "7,000.00 read from Sales 7,000.00"}), name))
    idx = lines.index("  business")
    self.assertEqual(lines[idx + 1:idx + 3], [f"    {'gross_income':<42}{'7,000.00':>14}", "        statement.txt, Sales 7,000.00"])

  def test_a_dotted_name_over_something_that_is_not_a_block_is_refused(self):
    for raw in ({"resident": True, "salary": 5, "sources": {"salary.x": "y"}},
                {"resident": True, "business": 5, "version": VERSION, "documents": {"a.txt": "form"},
                 "read": {"a.txt, business.gross_income": "1.00 read from Sales 1.00"}}):
      with self.subTest(raw): self.assertRaisesRegex(ValueError, "must be a JSON object", apart, raw)

  def test_confirming_a_figure_that_was_not_proposed_is_refused(self):
    with self.assertRaisesRegex(ValueError, "nothing is proposed for rent"): confirm(written(), "rent")

  def test_the_file_comes_back_the_way_it_went_in(self):
    raw = {"resident": True, "salary": Decimal("1107000.00"), "business": {"assets": [], "gross_income": 900000},
           "sources": {"salary": 'a "quoted" line'}, "proposed": {}}
    self.assertEqual(loaded(dumped(raw)), raw)

  def test_a_case_file_cannot_hold_what_json_has_no_word_for(self):
    with self.assertRaisesRegex(ValueError, "a case file cannot hold"): dumped({"salary": None})

  def test_a_figure_read_for_a_free_name_is_proposed_with_its_wording(self):
    text, how = noted(written(), STATEMENT, [], read=(("other_reliefs", "5,000.00 read from Relief claimed 5,000.00"),))
    _, held, proposed = apart(loaded(text))
    self.assertEqual((proposed["other_reliefs"], held["sources"]["other_reliefs"], tuple(newly(written(), text)), how.asked),
                     (Decimal(5000), "bank.txt, Relief claimed 5,000.00", ("other_reliefs",), ()))

  def test_a_second_document_adds_to_what_is_proposed(self):
    was = written(read={"statement.txt, rent": "40,000.00 read from Rent received 40,000.00"})
    rent = (("10,000.00 paid in on 05/07/2025, TENANT", "rent"), ("5,000.00 paid in on 05/08/2025, TENANT", "rent"))
    text, _ = noted(was, STATEMENT, [], labels=rent)
    _, held, proposed = apart(loaded(text))
    self.assertEqual((proposed["rent"], held["sources"]["rent"], tuple(newly(was, text))),
                     (Decimal(55000), "bank.txt, 2 labelled rent, statement.txt, Rent received 40,000.00", ("rent",)))

  def test_a_payment_whose_balance_does_not_agree_is_not_counted(self):
    line = "10,000.00 paid in on 05/07/2025, TENANT"
    raw = {"resident": True, "version": VERSION, "documents": {"bank.txt": "bank statement"}, "labels": {f"bank.txt, {line}": "rent"}}
    for more, want in (({}, {"rent": Decimal(10000)}), ({"checks": {f"bank.txt, {line}": "does not agree"}}, {})):
      with self.subTest(more): self.assertEqual(apart(raw | more)[2], want)

  def test_only_the_identical_line_that_does_not_agree_is_left_out(self):
    line = "10,000.00 paid in on 05/07/2025, TENANT"
    labels = {f"a.txt, {line}": "rent", f"a.txt, {line} (2)": "rent", f"b.txt, {line}": "rent"}
    for checks, source in (({f"a.txt, {line} (2)": "does not agree"}, "a.txt, 1 labelled rent, b.txt, 1 labelled rent"),
                           ({f"b.txt, {line}": "does not agree"}, "a.txt, 2 labelled rent")):
      documents = dict.fromkeys(("a.txt", "b.txt"), "bank statement")
      raw = {"resident": True, "version": VERSION, "documents": documents, "labels": labels, "checks": checks}
      _, held, proposed = apart(raw)
      with self.subTest(checks): self.assertEqual((proposed, held["sources"]["rent"]), ({"rent": Decimal(20000)}, source))

  def test_lines_whose_balance_was_not_checked_are_counted_and_named(self):
    lines = ("10,000.00 paid in on 05/07/2025, TENANT", "2,000.00 paid in on 05/08/2025, TENANT")
    raw = {"resident": True, "version": VERSION, "documents": {"bank.txt": "bank statement"},
           "labels": {f"bank.txt, {line}": "rent" for line in lines}, "checks": {f"bank.txt, {lines[1]}": "not checked"}}
    _, held, proposed = apart(raw)
    self.assertEqual((proposed, held["sources"]["rent"]), ({"rent": Decimal(12000)}, "bank.txt, 2 labelled rent, 1 unchecked"))

  def test_two_lines_labelled_alike_in_one_statement_are_summed(self):
    lines = ("10,000.00 paid in on 05/07/2025, TENANT", "2,012.50 paid in on 05/08/2025, TENANT", "500.00 paid in on 06/08/2025, CASH")
    raw = {"resident": True, "version": VERSION, "documents": {"bank.txt": "bank statement"},
           "labels": dict(zip([f"bank.txt, {line}" for line in lines], ("rent", "rent", "cash")))}
    self.assertEqual(derived(apart(raw)[1]), {"rent": (Decimal("12012.50"), "bank.txt, 2 labelled rent")})

  def test_every_kind_of_question_carries_a_plain_headline_and_plain_answers(self):
    salary = "money labelled pay came in and the case gives no salary"
    left = "12.00 paid in on 01/07/2025, SHOP"
    pension = "2,000.00 paid out in 2 payments that look like pension, in bank.pdf"
    loan = "18,000.00 paid out in 1 payment that looks like housing loan, in bank.pdf"
    old = "the balance after this does not agree, so it is left out: noted (it stays left out)"
    shown = case(json.dumps({"resident": True, "pending": {salary: "x", left: old, pension: "x", loan: "x"}}))
    self.assertEqual(shown["headlines"], {salary: "add your salary statement", left: "a payment was left out of the totals",
                                          pension: "were these paid into your own approved pension?", loan: "add your housing loan certificate"})
    self.assertTrue(shown["pending"][salary].endswith("; other (label it other instead)"))
    self.assertEqual(shown["pending"][left], "the balance after this does not agree, so it is left out: noted (leave it out)")
    self.assertTrue(shown["pending"][loan].endswith("; not (this was not for housing loan)"))

  def test_a_business_payment_question_carries_a_plain_headline(self):
    asked = "140.00 paid out in 2 payments that look like business expense, in bank.pdf"
    headlines = case(written(pending={asked: "pick the payments", "cash of 1,200.00 on 12/08/2025": "where did this come from"}))["headlines"]
    self.assertEqual(headlines, {asked: "which of these payments were costs of your business?"})

  def test_the_same_question_worded_differently_is_refused(self):
    asked = [("cash of 1,200.00 on 12/08/2025", "a different wording")]
    with self.assertRaisesRegex(ValueError, "already open with different wording"): noted(written(), STATEMENT, asked)

  def test_a_question_saved_in_older_words_is_the_same_question(self):
    salary = "money labelled pay came in and the case gives no salary"
    older = "add the statement: later (I'll add it later); not (this is not my salary)"
    newer = needing(spoken("labelling"), "pay")
    text, _ = noted(json.dumps({"resident": True, "pending": {salary: older}}), STATEMENT, [(salary, newer)])
    self.assertEqual(loaded(text)["pending"][salary], newer)

  def test_the_same_question_worded_the_same_changes_nothing(self):
    asked = [("cash of 1,200.00 on 12/08/2025", FACTS["pending"]["cash of 1,200.00 on 12/08/2025"])]
    self.assertEqual(loaded(noted(written(), STATEMENT, asked)[0])["pending"], FACTS["pending"])

  def test_a_question_already_answered_is_not_asked_again(self):
    was = "cash of 500.00 on 05/07/2025"
    text, how = noted(written(), STATEMENT, [(was, "what is this money")])
    self.assertEqual(loaded(text).get("pending"), FACTS["pending"])
    self.assertEqual((how.asked, how.answered), ((), (was,)))

  def test_a_document_is_remembered_by_its_fingerprint(self):
    text, _ = noted(written(), Document(name="payslip.txt", path="in/payslip.txt", mark=fingerprint(b"a line"), kind="payslip"), [])
    self.assertEqual(loaded(text)["texts"], {fingerprint(b"a line"): "payslip.txt"})

  def test_each_credit_is_kept_with_its_label_under_its_document(self):
    salary, interest = "5,000.00 paid in on 02/07/2025, SALARY", "12.50 paid in on 05/07/2025, INTEREST"
    text, _ = noted(written(labels={}), STATEMENT, [], ((salary, "pay"), (salary, "pay"), (interest, "interest")))
    where = STATEMENT.name
    self.assertEqual(loaded(text)["labels"], {f"{where}, {salary}": "pay", f"{where}, {salary} (2)": "pay", f"{where}, {interest}": "interest"})

  def test_the_document_that_was_read_is_recorded(self):
    text, _ = noted(written(), Document(name="payslip.txt", path="in/payslip.txt", mark="a mark", kind="payslip"), [])
    self.assertEqual(loaded(text)["documents"]["payslip.txt"], "payslip")

  def test_the_path_a_document_was_read_from_is_recorded(self):
    text, _ = noted(written(), Document(name="payslip.txt", path="in/payslip.txt", mark="a mark", kind="payslip"), [])
    self.assertEqual(loaded(text)["paths"], {"payslip.txt": "in/payslip.txt"})

  def test_the_case_comes_back_as_data(self):
    got = case(written())
    self.assertEqual(got["facts"]["salary"], "1107000")
    self.assertEqual((got["proposed"], got["changed"]), ({"other_income": "40000.00"}, {}))
    self.assertEqual(got["documents"], FACTS["documents"])
    self.assertIn("income tax", [fig["rule"] for fig in got["figures"]])

  def test_every_number_in_the_case_is_text(self):
    deep = case(written(business={"gross_income": 900000, "assets": [{"kind": "computer", "cost": 80000}]}))
    found, leaves = [deep["facts"], deep["proposed"], [fig["amount"] for fig in deep["figures"]]], []
    while found:
      one = found.pop()
      if isinstance(one, dict): found += list(one.values())
      elif isinstance(one, list): found += one
      else: leaves.append(one)
    for one in leaves:
      with self.subTest(one): self.assertIsInstance(one, (str, bool))

  def test_a_figure_comes_back_with_its_sections(self):
    tax = next(fig for fig in case(written())["figures"] if fig["rule"] == "income tax")
    self.assertEqual(tax["amount"], "49700")
    self.assertIn({"doc": "ita", "section": "s.4", "page": 26, "url": "https://www.mra.mu/download/ITAConsolidated.pdf#page=26"}, tax["sources"])

  def test_the_facts_come_back_the_way_a_person_reads_them(self):
    self.assertEqual([shown(True), shown(False), shown(Decimal("1107000"))], ["yes", "no", "1,107,000"])

  def test_business_lines_are_listed(self):
    ret = "\n".join(keep(written(business={"gross_income": 900000, "professional_expenses": 50000})))
    self.assertIn("  business", ret)
    self.assertIn("    gross_income", ret)

  def test_a_file_that_is_not_an_object_is_refused(self):
    with self.assertRaisesRegex(ValueError, "must be a JSON object"): keep("[]")

  def test_the_split_keeps_every_aside_part_out_of_the_facts(self):
    given, held, proposed = apart(json.loads(written()))
    self.assertEqual((set(given) & set(WORDING), sorted(held), list(held["documents"]), proposed),
                     (set(), sorted([*WORDING, "proposing"]), ["statement.txt"], {"other_income": Decimal(40000)}))

  def test_a_proposed_figure_is_shown_apart_from_the_facts(self):
    ret = keep(written())
    at = ret.index("figures proposed, not confirmed")
    self.assertEqual(ret[at + 1:at + 3], [f"  {'other_income':<44}{'40,000.00':>14}", "      statement.txt, Rent received 40,000.00"])

  def test_a_file_with_nothing_proposed_shows_no_such_heading(self):
    plain = written(read={"statement.txt, salary": FACTS["read"]["statement.txt, salary"]})
    self.assertNotIn("figures proposed, not confirmed", "\n".join(keep(plain)))

ASKED = "cash of 1,200.00 on 12/08/2025"

class TestAnswer(unittest.TestCase):
  def test_an_answer_moves_the_question_and_is_kept_word_for_word(self):
    held = json.loads(answer(written(), ASKED, "sold my old bicycle"))
    self.assertEqual(held["answers"][ASKED], "sold my old bicycle")
    self.assertNotIn(ASKED, held.get("pending", {}))

  def test_an_answer_already_given_stays_where_it_is(self):
    was = "cash of 500.00 on 05/07/2025"
    self.assertEqual(json.loads(answer(written(), ASKED, "a gift"))["answers"][was], FACTS["answers"][was])

  def test_an_answer_leaves_every_figure_alone(self):
    before = apart(loaded(written()))
    after = apart(loaded(answer(written(), ASKED, "a gift")))
    self.assertEqual((before[0], before[2]), (after[0], after[2]))

  def test_a_question_that_is_not_open_is_refused(self):
    with self.assertRaisesRegex(ValueError, "no open question where is my hat"): answer(written(), "where is my hat", "here")

  def test_a_blank_answer_is_refused(self):
    with self.assertRaisesRegex(ValueError, "is blank"): answer(written(), ASKED, "   ")

  def test_a_question_that_is_open_and_already_answered_keeps_the_first_words(self):
    both = written(answers={ASKED: "sold my old bicycle"})
    with self.assertRaisesRegex(ValueError, f"already answered {ASKED}"): answer(both, ASKED, "a loan from my brother")

TABLE = spoken("labelling")

class TestReceived(unittest.TestCase):
  LABELS = {"day.pdf, 1,000.00 paid in on 14/02/2025, SALARY": "pay", "day.pdf, 1,000.00 paid in on 03/03/2025, SALARY": "pay",
            "day.pdf, 250.50 paid in on 03/03/2025, SALARY (2)": "business", "day.pdf, 12.25 paid in on 29 Jun 25, INTEREST": "interest",
            "month.pdf, 5.00 paid in on 02/15/2025, REFUND": "other", "month.pdf, 7.00 paid in on 04/01/2025, REFUND": "other",
            "either.pdf, 400.00 paid in on 05/06/2025, TRANSFER": "other", "gone.pdf, 1.00 paid in on 01/01/2025, X": "other",
            "day.pdf, a lot paid in on 01/01/2025, X": "other", "day.pdf, 3.00 paid in on 20/05/2024, OLD": "other"}

  def held(self):
    return {"documents": dict.fromkeys(("day.pdf", "month.pdf", "either.pdf"), "bank statement"), "labels": self.LABELS, "year": {}, "outside": {}}

  def test_money_in_is_summed_by_kind_with_the_largest_first(self):
    self.assertEqual(received(self.held(), TABLE)["kinds"], {"pay": Decimal("2000.00"), "other": Decimal("412.00"), "business": Decimal("250.50"),
                                                        "interest": Decimal("12.25")})

  def test_a_statement_says_by_its_dates_which_part_is_the_month(self):
    got = received(self.held(), TABLE)["months"]
    self.assertEqual([got[m]["total"] for m in ("2025-02", "2025-04", "2025-06")], [Decimal("1005.00"), Decimal("7.00"), Decimal("12.25")])

  def test_the_income_year_runs_from_july_to_the_june_after_the_latest_payment(self):
    got = received(self.held(), TABLE)
    year = list(got["months"])
    self.assertEqual((year[0], year[-1], len(year)), ("2024-07", "2025-06", 12))
    self.assertEqual(got["months"]["2024-12"], {"total": Decimal("0.00"), "groups": {}, "payments": {}})

  def test_each_month_holds_its_total_its_groups_and_its_payments(self):
    self.assertEqual(received(self.held(), TABLE)["months"]["2025-03"],
                     {"total": Decimal("1250.50"), "groups": {"income": Decimal("1250.50")},
                      "payments": {"income": ["day.pdf, 1,000.00 paid in on 03/03/2025, SALARY",
                                              "day.pdf, 250.50 paid in on 03/03/2025, SALARY (2)"]}})

  def test_the_case_year_holds_the_months_whatever_the_latest_payment(self):
    got = received(self.held() | {"year": {"from": "2023-07", "to": "2024-06"}}, TABLE)
    self.assertEqual((list(got["months"])[0], "day.pdf, 3.00 paid in on 20/05/2024, OLD" in got["outside"]), ("2023-07", False))

  def test_a_payment_outside_the_year_is_not_counted(self):
    labels = {"day.pdf, 3.00 paid in on 20/05/2024, OLD": "other", "day.pdf, 1.00 paid in on 20/05/2025, NEW": "other"}
    self.assertEqual(received(self.held() | {"labels": labels}, TABLE)["kinds"], {"other": Decimal("1.00")})

  def test_a_payment_before_the_income_year_is_named(self):
    self.assertEqual(received(self.held(), TABLE)["outside"], ["day.pdf, 3.00 paid in on 20/05/2024, OLD"])

  def test_money_in_is_summed_by_what_it_counts_as(self):
    held = self.held() | {"labels": self.LABELS | {"month.pdf, 9.00 paid in on 04/01/2025, CASH": "cash"}}
    self.assertEqual(received(held, TABLE)["groups"], {"income": Decimal("2250.50"), "exempt": Decimal("12.25"), "unsorted": Decimal("9.00"),
                                                  "other": Decimal("412.00")})

  def test_each_kind_names_its_group(self):
    self.assertEqual(received(self.held(), TABLE)["group_of"], {"business": "income", "dividend": "income", "rent": "income", "pay": "income",
                                                              "interest": "exempt", "cash": "unsorted", "unclear": "unsorted", "other": "other"})

  def test_a_group_with_nothing_shows_zero_to_the_cent(self):
    self.assertEqual(str(received(self.held(), TABLE)["groups"]["unsorted"]), "0.00")

  def test_a_label_naming_no_known_kind_is_named_not_counted(self):
    held = self.held() | {"labels": {"day.pdf, 9.00 paid in on 01/01/2025, X": "gift"}}
    got = received(held, TABLE)
    self.assertEqual((got["unread"], got["kinds"]), (["day.pdf, 9.00 paid in on 01/01/2025, X"], {}))

  def test_a_date_that_reads_both_ways_is_not_placed_in_a_month(self):
    self.assertEqual(received(self.held(), TABLE)["undated"], ["either.pdf, 400.00 paid in on 05/06/2025, TRANSFER"])

  def test_a_label_that_does_not_read_as_money_paid_in_is_named(self):
    self.assertEqual(received(self.held(), TABLE)["unread"], ["gone.pdf, 1.00 paid in on 01/01/2025, X", "day.pdf, a lot paid in on 01/01/2025, X"])

  def test_keep_prints_money_in_and_names_what_it_left_out(self):
    text = dumped({"resident": True, "version": VERSION, "documents": self.held()["documents"], "labels": self.LABELS})
    out = keep(text)
    self.assertIn(f"  {'pay':<27}{'counts as income':<17}{'2,000.00':>14}", out)
    at = out.index(f"  {'exempt':<44}{'12.25':>14}")
    self.assertEqual(out[at + 1], "    ita Second Schedule Part II Sub-Part B item 3(c) page 267")
    self.assertIn("money paid in over the income year from 2024-07 to 2025-06, ita s.2 page 19, ita s.2 page 26", out)
    self.assertIn(f"  {'2025-03':<44}{'1,250.50':>14}", out)
    self.assertEqual(out[out.index("money paid in outside that income year") + 1], "  day.pdf, 3.00 paid in on 20/05/2024, OLD")
    self.assertEqual(out[out.index("money paid in with a date whose month is not clear") + 1], "  either.pdf, 400.00 paid in on 05/06/2025, TRANSFER")

  def test_the_case_as_json_carries_money_in_as_text_with_the_law_on_the_year(self):
    text = dumped({"resident": True, "version": VERSION, "documents": self.held()["documents"], "labels": self.LABELS})
    got = case(text)["received"]
    self.assertEqual((got["months"]["2025-04"]["total"], [s["page"] for s in got["year_sources"]]), ("7.00", [19, 26]))

class TestSet(unittest.TestCase):
  def test_an_amount_is_entered_with_its_source(self):
    got = loaded(set_fact(written(), "quarterly_tax_paid", "12,500.00"))
    self.assertEqual((got["quarterly_tax_paid"], got["sources"]["quarterly_tax_paid"]), (Decimal("12500.00"), "entered by you"))

  def test_a_count_and_a_yes_or_no_are_entered(self):
    got = loaded(set_fact(set_fact(written(), "dependants", "2"), "spouse_above_interest_bar", "Yes"))
    self.assertEqual((got["dependants"], got["spouse_above_interest_bar"]), (2, True))

  def test_a_business_line_is_entered_inside_the_business(self):
    self.assertEqual(loaded(set_fact(written(), "business.cost_of_sales", "4000"))["business"], {"cost_of_sales": Decimal("4000.00")})

  def test_an_entered_figure_replaces_its_proposal(self):
    self.assertNotIn("other_income", apart(loaded(set_fact(written(), "other_income", "35000")))[2])

  def test_an_entered_figure_keeps_the_reading_it_overrides(self):
    raw = loaded(set_fact(confirm(written(), "other_income"), "other_income", "35000"))
    self.assertEqual((raw["confirmed"]["other_income"], raw["other_income"], apart(raw)[2]), ("40000.00", 35000, {}))

  def test_an_entered_figure_is_proposed_again_when_a_document_reads_it_differently(self):
    text = set_fact(written(), "other_income", "35000")
    read = loaded(text)["read"] | {"statement.txt, other_income": "45,000.00 read from Rent received 45,000.00"}
    self.assertEqual(case(dumped(loaded(text) | {"read": read}))["changed"]["other_income"]["was"], "35000")

  def test_a_figure_written_in_by_hand_is_proposed_when_a_document_reads_it_differently(self):
    self.assertEqual(apart(loaded(written(other_income=35000)))[2], {"other_income": Decimal(40000)})

  def test_confirming_again_takes_the_new_source(self):
    text = confirm(written(), "other_income")
    read = loaded(text)["read"] | {"statement.txt, other_income": "45,000.00 read from Rent received 45,000.00"}
    again = loaded(confirm(dumped(loaded(text) | {"read": read}), "other_income"))
    self.assertEqual((again["other_income"], again["sources"]["other_income"]), (Decimal(45000), "statement.txt, Rent received 45,000.00"))

  def test_an_unknown_check_mark_is_refused(self):
    with self.assertRaisesRegex(ValueError, "unknown marks"): apart(loaded(written(checks={"bank.txt, 1.00 paid in on 01/07/2025, X": "fine"})))

  def test_a_garbled_confirmed_amount_is_refused(self):
    with self.assertRaisesRegex(ValueError, "confirmed holds a figure that is not an amount"): apart(loaded(written(confirmed={"salary": "abc"})))

  def test_a_check_for_a_document_the_case_never_read_is_refused(self):
    with self.assertRaisesRegex(ValueError, "unknown marks or documents"): apart(loaded(written(checks={"nowhere.txt, x": "not checked"})))

  def test_a_file_of_another_version_is_refused(self):
    later = json.dumps({"resident": True, "version": {"case": "9"}})
    with self.assertRaisesRegex(ValueError, "a case of version 9 cannot be read"): apart(loaded(later))

  def test_a_cleared_fact_is_gone_with_its_source(self):
    for name in ("dependants", "salary"):
      raw = loaded(set_fact(written(), name, ""))
      with self.subTest(name): self.assertEqual((name in raw, name in raw.get("sources", {})), (False, False))

  def test_a_cleared_business_line_leaves_the_rest_of_the_business(self):
    text = set_fact(set_fact(written(), "business.cost_of_sales", "4000"), "business.gross_income", "9000")
    self.assertEqual(apart(loaded(set_fact(text, "business.cost_of_sales", "")))[0]["business"], {"gross_income": Decimal("9000.00")})

  def test_an_unknown_fact_or_value_is_refused(self):
    for name, said, why in (("wealth", "1", "no fact wealth"), ("wealth", "", "no fact wealth"), ("business", "", "no fact business"),
                            ("dependants", "two", "takes a whole number"), ("rent", "-5", "not an amount"),
                            ("resident", "", "missing facts")):
      with self.subTest(name), self.assertRaisesRegex(ValueError, why): set_fact(written(), name, said)

  def test_a_fact_the_computation_refuses_is_not_kept(self):
    with self.assertRaisesRegex(ValueError, "school_fees"): set_fact(written(school_fees=[1000, 1000]), "dependants", "1")

class TestRemoved(unittest.TestCase):
  LINE = "9,000.00 paid in on 20/07/2025, CLIENT"
  CASE = {"resident": True, "version": {"case": "2"}, "documents": {"a.pdf": "bank statement", "b.pdf": "bank statement"},
          "paths": {"a.pdf": "/in/a.pdf", "b.pdf": "/in/b.pdf"}, "texts": {"m1": "a.pdf", "m2": "b.pdf"},
          "labels": {f"a.pdf, {LINE}": "business", "b.pdf, 100.00 paid in on 21/07/2025, FLAT": "rent",
                     "b.pdf, 5.00 paid in on 22/07/2025, X": "cash"},
          "paid": {"a.pdf, 40.00 paid out on 23/07/2025, STOCK": "business_expense"},
          "pending": {"5.00 paid in on 22/07/2025, X": "where did this cash come from",
                      "40.00 paid out in 1 payment that looks like business expense, in a.pdf": "which were costs"}}

  def test_a_removed_document_takes_what_was_read_from_it(self):
    _, held, proposed = apart(loaded(removed(dumped(self.CASE), "a.pdf")))
    self.assertEqual((list(held["documents"]), list(held["labels"]), held["paid"], list(held["texts"].values()), proposed),
                     (["b.pdf"], ["b.pdf, 100.00 paid in on 21/07/2025, FLAT", "b.pdf, 5.00 paid in on 22/07/2025, X"], {}, ["b.pdf"],
                      {"rent": Decimal("100.00")}))

  def test_questions_about_a_removed_document_are_dropped_and_the_rest_kept(self):
    held = apart(loaded(removed(dumped(self.CASE), "a.pdf")))[1]
    self.assertEqual(list(held["pending"]), ["5.00 paid in on 22/07/2025, X"])

  def test_a_confirmed_figure_from_a_removed_document_is_proposed_at_zero(self):
    confirmed = loaded(confirm(dumped(self.CASE), "business.gross_income"))
    self.assertEqual(apart(loaded(removed(dumped(confirmed), "a.pdf")))[2]["business.gross_income"], Decimal(0))

  def test_each_kind_of_question_about_a_removed_document_goes(self):
    raw = self.CASE | {"pending": {"money labelled pay came in and the case gives no salary": "add it",
                                   "1 payment in a.pdf looks like costs of a business, and the case has no business income": "say",
                                   "1 payment in b.pdf looks like costs of a business, and the case has no business income": "say",
                                   "7.00 on the line Other 7.00": "which line", "5.00 paid in on 22/07/2025, X": "where did this cash come from"}}
    raw["labels"] = raw["labels"] | {"a.pdf, 1.00 paid in on 24/07/2025, PAY": "pay"}
    held = apart(loaded(removed(dumped(raw), "a.pdf")))[1]
    self.assertEqual(sorted(held["pending"]), ["1 payment in b.pdf looks like costs of a business, and the case has no business income",
                                               "5.00 paid in on 22/07/2025, X"])

  def test_answers_about_a_removed_document_go_with_their_figures(self):
    question = "40.00 paid out in 1 payment that looks like business expense, in a.pdf"
    for said in ("yes", "payment 1"):
      raw = self.CASE | {"pending": {}, "answers": {question: said, "5.00 paid in on 22/07/2025, X": "a gift"}}
      _, held, proposed = apart(loaded(removed(dumped(raw), "a.pdf")))
      kept = (list(held["answers"]), "business.other_expenses" in proposed)
      with self.subTest(said): self.assertEqual(kept, (["5.00 paid in on 22/07/2025, X"], False))

  def test_an_answer_about_a_payment_in_a_removed_document_goes(self):
    raw = self.CASE | {"labels": self.CASE["labels"] | {"a.pdf, 7.00 paid in on 25/07/2025, Y": "other"},
                       "answers": {"7.00 paid in on 25/07/2025, Y": "gift", "money labelled pay came in and the case gives no salary": "business"}}
    self.assertEqual(apart(loaded(removed(dumped(raw), "a.pdf")))[1]["answers"], {})

  def test_a_form_that_shares_line_answers_with_another_cannot_be_removed(self):
    raw = self.CASE | {"documents": {"a.pdf": "statement_of_emoluments", "b.pdf": "statement_of_emoluments"}, "labels": {}, "paid": {},
                       "pending": {"7.00 on the line Other 7.00": "which line"}}
    with self.assertRaisesRegex(ValueError, "a.pdf shares form line answers with another form"): removed(dumped(raw), "a.pdf")

  def test_an_answer_about_a_kept_line_ending_in_a_bracketed_number_stays(self):
    line = "9.00 paid in on 20/07/2025, INVOICE (3)"
    raw = self.CASE | {"labels": self.CASE["labels"] | {f"b.pdf, {line}": "other"}, "answers": {line: "gift"}}
    self.assertEqual(apart(loaded(removed(dumped(raw), "a.pdf")))[1]["answers"], {line: "gift"})

  def test_a_document_the_case_does_not_hold_is_refused(self):
    with self.assertRaisesRegex(ValueError, "holds no document c.pdf"): removed(dumped(self.CASE), "c.pdf")

class TestYear(unittest.TestCase):
  def test_a_case_is_given_twelve_months_from_july(self):
    self.assertEqual(json.loads(with_year(written(), "2025-07"))["year"], {"from": "2025-07", "to": "2026-06"})

  def test_a_year_starts_in_july(self):
    with self.assertRaisesRegex(ValueError, "starts in month 7, not '2025-01'"): with_year(written(), "2025-01")

  def test_a_case_with_documents_keeps_its_year(self):
    text = with_year(written(), "2025-07")
    with self.assertRaisesRegex(ValueError, "already reads documents for the year from 2025-07"): with_year(text, "2024-07")

  def test_a_case_with_documents_and_no_year_can_be_given_one(self):
    self.assertEqual(json.loads(with_year(written(), "2024-07"))["year"]["to"], "2025-06")

  def test_a_year_that_is_not_twelve_months_is_refused(self):
    with self.assertRaisesRegex(ValueError, "year must be one income year"): apart(loaded(written(year={"from": "2025-07", "to": "2025-12"})))

class TestReanswered(unittest.TestCase):
  LINE = "10,000.00 on the line TOTAL 10,000.00"
  PAID = "100.00 paid in on 01/02/2026, TRANSFER"

  def test_a_changed_answer_moves_the_figure_worked_out_from_it(self):
    text = dumped({"resident": True, "answers": {self.LINE: "net_emoluments"}})
    held = loaded(reanswered(text, self.LINE, "total"))
    self.assertEqual((apart(loaded(text))[2], held["answers"][self.LINE], apart(held)[2]), ({"salary": Decimal(10000)}, "total", {}))

  def test_a_relabelled_payment_moves_its_amount_to_the_new_fact(self):
    text = dumped({"resident": True, "version": VERSION, "documents": {"bank.txt": "bank statement"}, "labels": {f"bank.txt, {self.PAID}": "rent"}})
    after = relabelled(text, [f"bank.txt, {self.PAID}"], "business")
    self.assertEqual((apart(loaded(text))[2], apart(loaded(after))[2]), ({"rent": Decimal(100)}, {"business.gross_income": Decimal(100)}))

  def test_a_question_never_answered_cannot_be_changed(self):
    with self.assertRaisesRegex(ValueError, "was never answered"): reanswered(dumped({"resident": True}), self.LINE, "total")

class TestPriced(unittest.TestCase):
  CASE = {"resident": True, "salary": 1000000, "business": {"gross_income": 100000}}

  def test_a_payment_is_priced_by_the_kind_it_could_be(self):
    text = json.dumps(self.CASE | {"pending": {"20,000.00 paid in on 12/01/2026, Transfer": "what was this payment for"}})
    got = priced(text)["20,000.00 paid in on 12/01/2026, Transfer"]
    self.assertEqual({k: v.amt for k, v in got.items()}, {"business": 4000, "interest": 0, "dividend": 0, "rent": 4000, "other": 0})

  def test_a_form_question_is_priced_by_the_line_each_answer_names(self):
    question = "10,000.00 on the line TOTAL 10,000.00"
    asks = "which line of the form is this: net_emoluments (the net pay); total (the whole pay)"
    got = priced(json.dumps(self.CASE | {"pending": {question: asks}}))[question]
    self.assertEqual({k: v.amt for k, v in got.items()}, {"net_emoluments": 2000, "total": 0})

  def test_keep_prints_each_answer_with_its_price(self):
    question = "20,000.00 paid in on 12/01/2026, Transfer"
    lines = keep(json.dumps(self.CASE | {"pending": {question: "what was this payment for"}}))
    shown = lines[lines.index("what each answer changes in the tax to pay") + 1:]
    self.assertEqual(shown[:2], [f"  {question}", f"    {'business':<30}{'+4,000':>14}"])
    self.assertIn(f"    {'other':<30}{'+0':>14}", shown)
    self.assertTrue(shown[2].strip().startswith("s."))

  def test_proposed_figures_stay_out_of_the_base(self):
    text = json.dumps({"resident": True, "salary": 400000, "version": VERSION, "documents": {"a.txt": "form"},
                       "read": {"a.txt, rent": "100,000.00 read from Rent 100,000.00"},
                       "pending": {"20,000.00 paid in on 12/01/2026, Transfer": "what was this payment for"}})
    rent = priced(text)["20,000.00 paid in on 12/01/2026, Transfer"]["rent"].amt
    self.assertEqual((apart(loaded(text))[2], rent), ({"rent": Decimal(100000)}, 0))

  def test_each_price_names_the_law_behind_it(self):
    question = "20,000.00 paid in on 12/01/2026, Transfer"
    src = priced(json.dumps(self.CASE | {"pending": {question: "what was this payment for"}}))[question]["business"].src
    self.assertIn(Source("ita", "s.4", 26), src)

if __name__ == "__main__": unittest.main()
