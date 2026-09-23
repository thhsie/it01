import json, unittest
from decimal import Decimal
from it01.keep import ASIDE, TITLES, WORDING, apart, confirm, dumped, figures, keep, loaded, noted, shown

FACTS = {"resident": True, "dependants": 1, "salary": 1107000, "paye_withheld": 71401,
         "sources": {"salary": "Total emoluments        1,107,000.00"},
         "answers": {"cash of 500.00 on 05/07/2025": "sold my old bicycle"},
         "documents": {"statement.txt": "statement of emoluments"},
         "pending": {"cash of 1,200.00 on 12/08/2025": "where did this come from"},
         "proposed": {"other_income": 40000}}

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
    plain = {k: v for k, v in rich.items() if k not in ASIDE}
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

  def test_a_source_naming_neither_a_fact_nor_a_proposed_figure_is_refused(self):
    with self.assertRaisesRegex(ValueError, "neither a fact nor a proposed figure"): keep(written(sources={"not_a_fact": "somewhere"}))

  def test_wording_that_is_not_text_is_refused(self):
    for part in WORDING:
      with self.subTest(part):
        with self.assertRaisesRegex(ValueError, "object of text"): keep(written(**{part: {"salary": 1}}))

  def test_a_facts_file_with_no_wording_still_makes_a_record(self):
    plain = {k: v for k, v in FACTS.items() if k not in ASIDE}
    ret = "\n".join(keep(json.dumps(plain)))
    self.assertIn("figures", ret)
    for title in TITLES.values(): self.assertNotIn(title, ret)

  def test_confirming_moves_a_figure_among_the_facts(self):
    raw = loaded(confirm(written(), "other_income"))
    self.assertEqual((raw["other_income"], "proposed" in raw, raw["sources"]["salary"]),
                     (Decimal(40000), False, "Total emoluments        1,107,000.00"))

  def test_confirming_one_of_two_leaves_the_other_proposed(self):
    two = written(proposed={"other_income": 40000, "other_reliefs": 5000})
    self.assertEqual(loaded(confirm(two, "other_income"))["proposed"], {"other_reliefs": Decimal(5000)})

  def test_confirming_a_figure_that_was_not_proposed_is_refused(self):
    with self.assertRaisesRegex(ValueError, "nothing is proposed for rent"): confirm(written(), "rent")

  def test_the_file_comes_back_the_way_it_went_in(self):
    raw = {"resident": True, "salary": Decimal("1107000.00"), "business": {"assets": [], "gross_income": 900000},
           "sources": {"salary": 'a "quoted" line'}, "proposed": {}}
    self.assertEqual(loaded(dumped(raw)), raw)

  def test_a_case_file_cannot_hold_what_json_has_no_word_for(self):
    with self.assertRaisesRegex(ValueError, "a case file cannot hold"): dumped({"salary": None})

  def test_a_figure_read_for_a_free_name_is_proposed_with_its_wording(self):
    text, how = noted(written(), {"other_reliefs": (Decimal(5000), "Relief claimed 5,000.00")}, {}, [])
    raw = loaded(text)
    self.assertEqual((raw["proposed"]["other_reliefs"], raw["sources"]["other_reliefs"], how.proposed, how.asked),
                     (Decimal(5000), "Relief claimed 5,000.00", ("other_reliefs",), ()))

  def test_a_second_document_adds_to_what_is_proposed(self):
    was = written(sources=FACTS["sources"] | {"other_income": "Rent received 40,000.00"})
    text, how = noted(was, {"other_income": (Decimal(15000), "2 labelled rent")}, {"q2.txt": "bank statement"}, [])
    raw = loaded(text)
    self.assertEqual((raw["proposed"]["other_income"], raw["sources"]["other_income"], how.proposed),
                     (Decimal(55000), "Rent received 40,000.00, 2 labelled rent", ("other_income",)))

  def test_two_documents_asking_about_one_fact_do_not_collide(self):
    one, _ = noted(written(), {"salary": (Decimal(1107000), "q1 line")}, {"q1.txt": "payslip"}, [])
    two, how = noted(one, {"salary": (Decimal(1107000), "q2 line")}, {"q2.txt": "payslip"}, [])
    self.assertEqual(len(how.asked), 1)
    self.assertEqual(len([q for q in loaded(two)["pending"] if q.startswith("salary read as")]), 2)

  def test_a_figure_for_a_confirmed_fact_is_asked_about(self):
    for amt in (Decimal(9), Decimal(1107000)):
      with self.subTest(amt):
        text, how = noted(written(), {"salary": (amt, "a payslip line")}, {}, [])
        asked = f"salary read as {amt:,} in a payslip line, and the file already gives 1,107,000"
        self.assertEqual(loaded(text)["pending"][asked], "add it to the fact, or leave the fact if this is the same money read twice")
        self.assertEqual((how.proposed, how.asked), ((), (asked,)))

  def test_the_same_question_worded_differently_is_refused(self):
    asked = [("cash of 1,200.00 on 12/08/2025", "a different wording")]
    with self.assertRaisesRegex(ValueError, "already open with different wording"): noted(written(), {}, {}, asked)

  def test_the_same_question_worded_the_same_changes_nothing(self):
    asked = [("cash of 1,200.00 on 12/08/2025", FACTS["pending"]["cash of 1,200.00 on 12/08/2025"])]
    self.assertEqual(loaded(noted(written(), {}, {}, asked)[0])["pending"], FACTS["pending"])

  def test_the_document_that_was_read_is_recorded(self):
    text, _ = noted(written(), {}, {"payslip.txt": "payslip"}, [])
    self.assertEqual(loaded(text)["documents"]["payslip.txt"], "payslip")

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
    self.assertEqual((set(given) & set(ASIDE), sorted(held), list(held["documents"]), proposed),
                     (set(), sorted(WORDING), ["statement.txt"], {"other_income": Decimal(40000)}))

  def test_a_proposed_figure_is_shown_apart_from_the_facts(self):
    ret = keep(written(sources={"other_income": "Rent received 40,000.00"}))
    at = ret.index("figures proposed, not confirmed")
    self.assertEqual(ret[at + 1], "  other_income                                        40,000")
    self.assertEqual(ret[at + 2], "      Rent received 40,000.00")

  def test_a_file_with_nothing_proposed_shows_no_such_heading(self):
    plain = {k: v for k, v in FACTS.items() if k != "proposed"}
    self.assertNotIn("figures proposed, not confirmed", "\n".join(keep(json.dumps(plain))))

  def test_a_proposed_figure_that_is_already_a_fact_is_refused(self):
    with self.assertRaisesRegex(ValueError, "repeats facts already given \\['salary'\\]"): keep(written(proposed={"salary": 2000000}))

  def test_proposed_written_as_null_is_refused(self):
    with self.assertRaisesRegex(ValueError, "object of figures"): keep(written(proposed=None))

  def test_a_proposed_figure_that_is_not_a_fact_name_is_refused(self):
    with self.assertRaisesRegex(ValueError, "not facts \\['not_a_fact'\\]"): keep(written(proposed={"not_a_fact": 1}))

  def test_a_proposed_figure_that_is_not_an_amount_is_refused(self):
    for bad in (True, "40000", 1.555, -1):
      with self.subTest(bad):
        with self.assertRaisesRegex(ValueError, "invalid proposed other_income"): keep(written(proposed={"other_income": bad}))

if __name__ == "__main__": unittest.main()
