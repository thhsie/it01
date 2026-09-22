import json, unittest
from decimal import Decimal
from it01.keep import ASIDE, TITLES, apart, figures, keep, loaded, shown

FACTS = {"resident": True, "dependants": 1, "salary": 1107000, "paye_withheld": 71401,
         "sources": {"salary": "Total emoluments        1,107,000.00"},
         "answers": {"cash of 500.00 on 05/07/2025": "sold my old bicycle"},
         "documents": {"statement.txt": "statement of emoluments"},
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

  def test_a_source_for_a_fact_that_was_not_given_is_refused(self):
    with self.assertRaisesRegex(ValueError, "not given"): keep(written(sources={"rent": "somewhere"}))

  def test_wording_that_is_not_text_is_refused(self):
    for part in ASIDE:
      with self.subTest(part):
        with self.assertRaisesRegex(ValueError, "object of text"): keep(written(**{part: {"salary": 1}}))

  def test_a_facts_file_with_no_wording_still_makes_a_record(self):
    plain = {k: v for k, v in FACTS.items() if k not in ASIDE}
    ret = "\n".join(keep(json.dumps(plain)))
    self.assertIn("figures", ret)
    for title in TITLES.values(): self.assertNotIn(title, ret)

  def test_the_facts_come_back_the_way_a_person_reads_them(self):
    self.assertEqual([shown(True), shown(False), shown(Decimal("1107000"))], ["yes", "no", "1,107,000"])

  def test_business_lines_are_listed(self):
    ret = "\n".join(keep(written(business={"gross_income": 900000, "professional_expenses": 50000})))
    self.assertIn("  business", ret)
    self.assertIn("    gross_income", ret)

  def test_a_file_that_is_not_an_object_is_refused(self):
    with self.assertRaisesRegex(ValueError, "must be a JSON object"): keep("[]")

  def test_the_split_keeps_every_aside_part_out_of_the_facts(self):
    given, held = apart(json.loads(written()))
    self.assertEqual((set(given) & set(ASIDE), sorted(held), list(held["documents"])),
                     (set(), sorted(ASIDE), ["statement.txt"]))

if __name__ == "__main__": unittest.main()
