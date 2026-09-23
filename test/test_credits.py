import json, unittest
from decimal import Decimal
from unittest import mock
from it01.rows import Check
from it01.credits import ADRIFT, asked, fed, listed, named, received, spoken, totals
from it01.tax import AMOUNTS

PAID_IN = """\
Date        Description                    Debit       Credit      Balance
01/07/2025  Opening balance                                       1,000.00
02/07/2025  SALARY JULY ACME LTD                     5,000.00      6,000.00
03/07/2025  Rent                          1,500.00                 4,500.00
04/07/2025  INTEREST PAID                               12.50      4,512.50
05/07/2025  CASH DEPOSIT                               500.00      5,012.50
"""

OFF_BY = """\
Date        Description                    Debit       Credit      Balance
01/07/2025  Opening balance                                       1,000.00
02/07/2025  RENT JULY                                2,000.00      3,000.00
03/07/2025  Shop                          1,000.00                 2,000.00
04/07/2025  RENT AUGUST                              2,000.00      4,000.00
05/07/2025  Shop                            500.00                 3,500.00
06/07/2025  RENT SEPTEMBER                           2,000.00      5,600.00
"""

CALLED, KINDS, FEEDS, ASKING = spoken("labelling")

def reply(*names:str) -> str: return json.dumps({str(n): name for n, name in enumerate(names, 1)})

class TestCredits(unittest.TestCase):
  def test_a_labelling_file_says_what_it_reads(self):
    self.assertEqual(CALLED, "bank statement")

  def test_a_kind_that_feeds_a_fact_totals_its_credits(self):
    found = named(received(PAID_IN), reply("rent", "rent", "cash"), KINDS)
    self.assertEqual(fed(found, FEEDS)[0], {"rent": (Decimal("5012.50"), "2 labelled rent")})

  def test_a_credit_whose_balance_does_not_agree_is_left_out_and_asked_about(self):
    found = named(received(OFF_BY), reply("rent", "rent", "rent"), KINDS)
    seen, adrift = fed(found, FEEDS)
    self.assertEqual(seen, {"rent": (Decimal("4000.00"), "2 labelled rent")})
    self.assertEqual([(q.amt, q.description, q.asking) for q in adrift], [(Decimal("2000.00"), "RENT SEPTEMBER", ADRIFT)])

  def test_a_kind_that_feeds_nothing_proposes_nothing(self):
    found = named(received(PAID_IN), reply("pay", "interest", "cash"), KINDS)
    self.assertEqual(fed(found, FEEDS), ({}, ()))

  def test_a_feeds_table_that_does_not_hold_up_is_refused(self):
    base = {"name": "a statement", "kinds": {"one": "a", "two": "b", "three": "c"}, "asking": {"three": "what is this"}}
    for feeds, says in (({"nope": "salary"}, "feeds from unknown kinds"), ({"one": "nope"}, "feeds unknown facts"),
                        ({"three": "salary"}, "both feeds and asks about"), ({"one": "salary", "two": "salary"}, "more than one kind"),
                        ("not an object", "object of names")):
      with self.subTest(says), mock.patch("it01.credits.data", return_value=base | {"feeds": feeds}):
        with self.assertRaisesRegex(ValueError, says): spoken("labelling")

  def test_a_labelling_file_with_no_feeds_proposes_nothing(self):
    base = {"name": "a statement", "kinds": {"one": "a"}, "asking": {"one": "what is this"}}
    with mock.patch("it01.credits.data", return_value=base): self.assertEqual(spoken("labelling")[2], {})

  def test_the_shipped_table_feeds_only_kinds_and_facts(self):
    for kind, fact in FEEDS.items():
      with self.subTest(kind):
        self.assertIn(kind, KINDS)
        self.assertIn(fact, AMOUNTS)
        self.assertNotIn(kind, ASKING)

  def test_only_money_paid_in_is_labelled(self):
    self.assertEqual([e.paid_in for e in received(PAID_IN)], [Decimal("5000.00"), Decimal("12.50"), Decimal("500.00")])

  def test_the_credits_are_numbered_for_the_model(self):
    self.assertEqual(listed(received(PAID_IN)).split("\n")[0], "1. 02/07/2025 5,000.00 SALARY JULY ACME LTD")

  def test_each_credit_takes_the_kind_it_was_given(self):
    got = named(received(PAID_IN), reply("pay", "interest", "cash"), KINDS)
    self.assertEqual([(c.amt, c.kind) for c in got],
                     [(Decimal("5000.00"), "pay"), (Decimal("12.50"), "interest"), (Decimal("500.00"), "cash")])

  def test_an_answer_that_does_not_cover_every_credit_is_refused(self):
    with self.assertRaisesRegex(ValueError, r"answered for \['1', '2'\] and there are 3"): named(received(PAID_IN), reply("pay", "interest"), KINDS)

  def test_a_kind_that_is_not_in_the_list_is_refused(self):
    with self.assertRaisesRegex(ValueError, "unknown kind"): named(received(PAID_IN), reply("pay", "interest", "windfall"), KINDS)

  def test_an_answer_that_is_not_json_is_refused(self):
    with self.assertRaisesRegex(ValueError, "did not answer with JSON"): named(received(PAID_IN), "pay, interest, cash", KINDS)

  def test_an_answer_that_is_not_an_object_is_refused(self):
    with self.assertRaisesRegex(ValueError, "must answer with a JSON object"): named(received(PAID_IN), '["pay"]', KINDS)

  def test_the_kinds_that_only_the_taxpayer_knows_become_questions(self):
    got = named(received(PAID_IN), reply("pay", "unclear", "cash"), KINDS)
    self.assertEqual([(q.amt, q.asking) for q in asked(got, ASKING)],
                     [(Decimal("12.50"), ASKING["unclear"]), (Decimal("500.00"), ASKING["cash"])])

  def test_a_credit_with_a_settled_kind_raises_no_question(self):
    got = named(received(PAID_IN), reply("pay", "interest", "business"), KINDS)
    self.assertEqual(asked(got, ASKING), ())

  def test_credits_of_one_kind_are_added_together(self):
    got = named(received(PAID_IN), reply("pay", "pay", "interest"), KINDS)
    self.assertEqual(totals(got), {"pay": Decimal("5012.50"), "interest": Decimal("500.00")})

  def test_a_kind_nothing_was_given_is_left_out_of_the_totals(self):
    got = named(received(PAID_IN), reply("pay", "pay", "pay"), KINDS)
    self.assertEqual(list(totals(got)), ["pay"])

  def test_the_order_the_answer_comes_in_does_not_matter(self):
    jumbled = json.dumps({"3": "cash", "1": "pay", "2": "interest"})
    self.assertEqual([c.kind for c in named(received(PAID_IN), jumbled, KINDS)], ["pay", "interest", "cash"])

  def test_a_kind_that_is_not_a_name_is_refused(self):
    muddled = json.dumps({"1": ["pay"], "2": "interest", "3": "cash"})
    with self.assertRaisesRegex(ValueError, "unknown kind"): named(received(PAID_IN), muddled, KINDS)

  def test_a_credit_carries_whether_its_balance_agreed(self):
    self.assertTrue(all(c.check is Check.AGREES for c in named(received(PAID_IN), reply("pay", "pay", "pay"), KINDS)))

  def test_every_kind_that_raises_a_question_is_a_kind(self):
    for kind in ASKING: self.assertIn(kind, KINDS)

if __name__ == "__main__": unittest.main()
