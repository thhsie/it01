import unittest
from decimal import Decimal
from it01.rows import Check, dropped, entries, is_statement

SIDE_BY_SIDE = """\
Date        Description                    Debit       Credit      Balance
01/07/2025  Opening balance                                       1,000.00
02/07/2025  Salary                                   5,000.00      6,000.00
03/07/2025  Rent                          1,500.00                 4,500.00
04/07/2025  Fees                            200.00                 4,300.00
05/07/2025  Interest                                    12.50      4,312.50
"""

TWO_LINES = """\
Date        Description                   Debit        Credit      Balance
01 Jul 25   BROUGHT FORWARD
                                                                   1,000.00
02 Jul 25   DIRECT CREDIT                             5,000.00
            ACME LTD                                               6,000.00
03 Jul 25   CARD PURCHASE                 1,500.00
            SOME SHOP                                              4,500.00
04 Jul 25   CARD PURCHASE                   500.00
            OTHER SHOP                                             4,000.00
"""

SECOND_PAGE = SIDE_BY_SIDE + """\f
Date        Description                   Credit        Debit      Balance
06/07/2025  Refund                         12.50                   4,325.00
07/07/2025  Charges                                     25.00      4,300.00
08/07/2025  Transfer in                 1,000.00                   5,300.00
09/07/2025  Standing order                             300.00      5,000.00
"""

ONE_FEE = """\
Date        Description                    Debit       Credit      Balance
01/07/2025  Opening balance                                       1,000.00
02/07/2025  Salary                                   5,000.00      6,000.00
03/07/2025  Refund                                   1,500.00      7,500.00
04/07/2025  Fees                            200.00                 7,300.00
05/07/2025  Interest                                    12.50      7,312.50
"""

NO_BALANCE_PAGE = """\
\fDate        Description                    Debit       Credit
06/07/2025  Refund                                     111.11
07/07/2025  Charges                       222.22
"""

DEBITS_ONLY = """\
Date        Description                    Debit       Credit      Balance
01/07/2025  Opening balance                                       5,000.00
02/07/2025  Rent                          1,500.00                 3,500.00
03/07/2025  Fees                            200.00                 3,300.00
04/07/2025  Card                            300.00                 3,000.00
"""

BRACKETED = """\
Date        Description                    Debit       Credit      Balance
01/07/2025  Opening balance                                       1,000.00
02/07/2025  Rent                          1,500.00                 -500.00
03/07/2025  Refund                          (100.00)               -400.00
04/07/2025  Fees                            200.00                 -600.00
05/07/2025  Card                            300.00                 -900.00
"""

BOTH_WAYS = """\
Date        Description                    Debit       Credit      Balance
01/07/2025  Opening balance                                       1,000.00
02/07/2025  Salary                                   5,000.00      6,000.00
03/07/2025  Rent                                     1,500.00      4,500.00
04/07/2025  Fees                            200.00                 4,300.00
05/07/2025  Card                            300.00                 4,000.00
"""

def instead(amount:str) -> str:
  line = next(row for row in SIDE_BY_SIDE.split("\n") if "Rent" in row)
  at = line.index("1,500.00") + len("1,500.00")
  return SIDE_BY_SIDE + "            Reference".ljust(at - len(amount)) + amount + "\n"

def under(out:str, into:str, off:int=0) -> str:
  head, rest = SIDE_BY_SIDE.split("\n", 1)
  ends = [head.index(word) + len(word) - off for word in ("Debit", "Credit", "Balance")]
  line = [" "] * (max(ends) + 1)
  for word, end in zip((out, into, "Balance"), ends): line[end - len(word):end] = word
  return "".join(line) + "\n" + rest

class TestRows(unittest.TestCase):
  def test_reads_a_statement_laid_out_in_columns(self):
    self.assertEqual([(e.paid_out, e.paid_in, e.balance) for e in entries(SIDE_BY_SIDE)],
                     [(None, Decimal("5000.00"), Decimal("6000.00")), (Decimal("1500.00"), None, Decimal("4500.00")),
                      (Decimal("200.00"), None, Decimal("4300.00")), (None, Decimal("12.50"), Decimal("4312.50"))])

  def test_reads_a_statement_where_the_balance_is_on_the_next_line(self):
    self.assertEqual([(e.paid_out, e.paid_in, e.balance) for e in entries(TWO_LINES)],
                     [(None, Decimal("5000.00"), Decimal("6000.00")), (Decimal("1500.00"), None, Decimal("4500.00")),
                      (Decimal("500.00"), None, Decimal("4000.00"))])

  def test_every_balance_is_checked_against_the_running_total(self):
    for text in (SIDE_BY_SIDE, TWO_LINES):
      with self.subTest(text[:20]): self.assertTrue(all(e.check is Check.AGREES for e in entries(text)))

  def test_a_balance_that_does_not_follow_is_reported(self):
    broken = SIDE_BY_SIDE.replace("4,312.50", "9,999.99")
    self.assertEqual([e.check for e in entries(broken)], [Check.AGREES, Check.AGREES, Check.AGREES, Check.DIFFERS])

  def test_columns_are_read_again_on_each_page(self):
    got = entries(SECOND_PAGE)
    self.assertEqual([(e.paid_out, e.paid_in) for e in got[-4:]],
                     [(None, Decimal("12.50")), (Decimal("25.00"), None), (None, Decimal("1000.00")), (Decimal("300.00"), None)])
    self.assertTrue(all(e.check is Check.AGREES for e in got))

  def test_one_transaction_may_be_paid_out_and_in(self):
    both = SIDE_BY_SIDE.replace("03/07/2025  Rent                          1,500.00                 4,500.00",
                                "03/07/2025  Rent                          1,600.00      100.00     4,500.00")
    got = entries(both)
    self.assertEqual((got[1].paid_out, got[1].paid_in, got[1].check), (Decimal("1600.00"), Decimal("100.00"), Check.AGREES))

  def test_the_date_and_description_come_from_the_lines_of_the_entry(self):
    got = entries(TWO_LINES)
    self.assertEqual((got[0].date, got[0].description), ("02 Jul 25", "DIRECT CREDIT ACME LTD"))

  def test_an_amount_with_no_balance_to_check_it_is_marked(self):
    trailing = SIDE_BY_SIDE + "06/07/2025  Cheque                          400.00\n"
    self.assertEqual(entries(trailing)[-1].check, Check.UNCHECKED)

  def test_a_total_under_the_last_balance_is_not_a_transaction(self):
    totalled = SIDE_BY_SIDE + "            Total                         1,700.00    5,012.50\n"
    self.assertEqual(entries(totalled), entries(SIDE_BY_SIDE))

  def test_a_dated_line_or_a_single_amount_under_the_last_balance_stays(self):
    cheque = "06/07/2025  Cheque                        1,700.00\n"
    for text, tail in ((SIDE_BY_SIDE, cheque), (ONE_FEE, "            Total                           200.00\n")):
      with self.subTest(tail): self.assertEqual(entries(text + tail)[-1].check, Check.UNCHECKED)

  def test_a_statement_with_no_running_balance_is_refused(self):
    with self.assertRaisesRegex(ValueError, "no running balance column"): entries("Salary 5,000.00\nRent 1,500.00\n")

  def test_a_document_with_no_amounts_is_refused(self):
    with self.assertRaisesRegex(ValueError, "no running balance column"): entries("Nothing here at all\n")

  def test_a_summary_above_the_headings_does_not_hide_them(self):
    summarised = "Opening balance 1,000.00 Closing balance 4,312.50\n" + SIDE_BY_SIDE
    self.assertEqual([e.paid_in for e in entries(summarised)][1], Decimal("5000.00"))

  def test_a_carried_balance_is_not_printed_as_a_transaction(self):
    last = SIDE_BY_SIDE.rstrip("\n").split("\n")[-1]
    at = last.rindex("4,312.50")
    carried = SIDE_BY_SIDE + "            Balance carried forward".ljust(at) + last[at:] + "\n"
    self.assertEqual(len(entries(carried)), len(entries(SIDE_BY_SIDE)))

  def test_the_headings_say_which_way_the_money_moved(self):
    swapped = SIDE_BY_SIDE.replace("Debit       Credit", "Credit       Debit")
    got = entries(swapped)
    self.assertEqual([(e.paid_out, e.paid_in) for e in got],
                     [(Decimal("5000.00"), None), (None, Decimal("1500.00")), (None, Decimal("200.00")), (Decimal("12.50"), None)])
    self.assertTrue(all(e.check is Check.AGREES for e in got))

  def test_every_heading_in_the_table_is_read(self):
    for out, into in (("Debit", "Credit"), ("Withdrawals", "Deposits"), ("Money out", "Money in"), ("Paid out", "Paid in")):
      with self.subTest(out): self.assertEqual(entries(under(out, into))[1].paid_out, Decimal("1500.00"))

  def test_a_statement_with_no_headings_is_refused(self):
    bare = "\n".join(SIDE_BY_SIDE.split("\n")[1:])
    with self.assertRaisesRegex(ValueError, "which way the money moved"): entries(bare)

  def test_headings_that_disagree_with_each_other_are_refused(self):
    muddled = SIDE_BY_SIDE.replace("Debit       Credit", "Debit        Debit")
    with self.assertRaisesRegex(ValueError, "which way the money moved"): entries(muddled)

  def test_a_figure_that_is_not_money_is_not_read(self):
    for shown in ("1,234,567", "5.00%"):
      with self.subTest(shown): self.assertEqual(len(entries(instead(shown))), len(entries(SIDE_BY_SIDE)))

  def test_an_amount_may_be_bracketed_or_trail_a_minus(self):
    for shown in ("(1,500.00)", "1,500.00-"):
      with self.subTest(shown):
        marked = SIDE_BY_SIDE.replace("  1,500.00", f"{shown:>10}")
        self.assertEqual(entries(marked)[1].paid_out, Decimal("1500.00"))

  def test_a_repeated_balance_does_not_count_against_the_page(self):
    still = SIDE_BY_SIDE.replace("02/07/2025  Salary                                   5,000.00      6,000.00",
                                 "02/07/2025  Nothing happened                                      1,000.00")
    self.assertEqual([e.paid_out for e in entries(still)], [Decimal("1500.00"), Decimal("200.00"), None])

  def test_a_column_of_two_amounts_is_not_a_running_balance(self):
    short = "\n".join(SIDE_BY_SIDE.split("\n")[:3]) + "\n"
    with self.assertRaisesRegex(ValueError, "no running balance column"): entries(short)

  def test_a_page_too_short_to_work_out_does_not_vote(self):
    tail = SIDE_BY_SIDE + "\f\nDate        Description                   Credit        Debit      Balance\n" \
           "06/07/2025  Charges                                     12.50      4,300.00\n"
    self.assertEqual([e.paid_out for e in entries(tail)][:2], [None, Decimal("1500.00")])

  def test_a_row_naming_fewer_columns_does_not_overrule_the_headings(self):
    head = SIDE_BY_SIDE.split("\n")[0]
    decoy = " " * (head.index("Debit") - 1) + "Credit\n" + SIDE_BY_SIDE
    self.assertEqual(entries(decoy)[1].paid_out, Decimal("1500.00"))

  def test_two_rows_naming_the_columns_in_opposite_orders_are_refused(self):
    head = SIDE_BY_SIDE.split("\n")[0]
    swapped = head.replace("Debit", "XXXXX").replace("Credit", "Debit").replace("XXXXX", "Credit")
    with self.assertRaisesRegex(ValueError, "disagree about which way"): entries(swapped + "\n" + SIDE_BY_SIDE)

  def test_a_heading_too_far_from_its_column_is_not_used(self):
    self.assertEqual(entries(under("Debit", "Credit", 3))[1].paid_out, Decimal("1500.00"))
    with self.assertRaisesRegex(ValueError, "which way the money moved"): entries(under("Debit", "Credit", 20))

  def test_a_column_that_explains_half_its_changes_is_not_the_balance(self):
    half = SIDE_BY_SIDE.replace("1,500.00", "1,499.00").replace("  200.00", "  199.00")
    with self.assertRaisesRegex(ValueError, "no running balance column"): entries(half)

  def test_a_column_pointing_both_ways_is_left_out(self):
    got = entries(BOTH_WAYS)
    self.assertEqual((got[1].paid_out, got[1].paid_in, got[1].check), (None, None, Check.DIFFERS))

  def test_thousands_may_be_separated_by_a_dot_or_a_space(self):
    for shown, plain in (("1.500,00", "1,500.00"), ("1 500.00", "1,500.00")):
      with self.subTest(shown): self.assertEqual(entries(SIDE_BY_SIDE.replace(plain, shown))[1].paid_out, Decimal("1500.00"))

  def test_an_amount_explains_one_change_only(self):
    twice = SIDE_BY_SIDE.replace("04/07/2025  Fees                            200.00                 4,300.00",
                                 "04/07/2025  Fees                            200.00                 4,300.00\n"
                                 "05/07/2025  Fees again                      200.00                 4,100.00")
    self.assertEqual([e.paid_out for e in entries(twice)][2:4], [Decimal("200.00"), Decimal("200.00")])

  def test_a_heading_over_an_empty_column_is_not_used(self):
    self.assertEqual([e.paid_out for e in entries(DEBITS_ONLY)], [Decimal("1500.00"), Decimal("200.00"), Decimal("300.00")])

  def test_an_overdrawn_balance_keeps_its_sign(self):
    self.assertEqual([e.balance for e in entries(BRACKETED)][:2], [Decimal("-500.00"), Decimal("-400.00")])

  def test_a_carried_balance_that_does_not_follow_is_reported(self):
    last = SIDE_BY_SIDE.rstrip("\n").split("\n")[-1]
    at = last.rindex("4,312.50")
    carried = SIDE_BY_SIDE + "            Balance carried forward".ljust(at) + "9,999.99" + "\n"
    self.assertEqual(entries(carried)[-1].check, Check.DIFFERS)

  def test_a_form_feed_may_start_the_line_it_breaks_on(self):
    joined = SIDE_BY_SIDE + "\f" + SECOND_PAGE[SECOND_PAGE.index("\f") + 2:]
    self.assertEqual(len(entries(joined)), len(entries(SECOND_PAGE)))

  def test_a_bracketed_amount_does_not_split_its_column(self):
    got = entries(BRACKETED)
    self.assertEqual([e.paid_out for e in got], [Decimal("1500.00"), Decimal("100.00"), Decimal("200.00"), Decimal("300.00")])
    self.assertEqual([e.check for e in got], [Check.AGREES, Check.DIFFERS, Check.AGREES, Check.AGREES])

  def test_a_subtotal_makes_the_transaction_after_it_not_agree(self):
    total = SIDE_BY_SIDE.replace("05/07/2025  Interest", "            Total debits                  1,700.00\n05/07/2025  Interest")
    got = entries(total)
    self.assertEqual((got[2].paid_out, got[2].check), (Decimal("200.00"), Check.AGREES))
    self.assertEqual((got[3].paid_out, got[3].check), (Decimal("1700.00"), Check.DIFFERS))

  def test_a_page_with_no_running_balance_is_skipped(self):
    head = SIDE_BY_SIDE.split("\n")[0]
    at = head.index("Debit") + len("Debit")
    summary = SIDE_BY_SIDE + "\fAccount summary\n" + "Total paid out".ljust(at - 8) + "1,700.00\n" + "Total paid in".ljust(at - 8) + "5,012.50\n"
    self.assertEqual(len(entries(summary)), len(entries(SIDE_BY_SIDE)))

  def test_the_amounts_a_page_loses_are_counted(self):
    self.assertEqual(dropped(SIDE_BY_SIDE + NO_BALANCE_PAGE), {2: 2})

  def test_a_page_that_does_not_repeat_its_headings_is_counted_too(self):
    bare = SIDE_BY_SIDE + "\f" + "\n".join(NO_BALANCE_PAGE.split("\n")[1:])
    self.assertEqual(dropped(bare), {2: 2})

  def test_a_statement_is_told_by_its_running_balance(self):
    bare = "Date        Description\n" + "\n".join(SIDE_BY_SIDE.split("\n")[1:])
    for name, text, holds in (("side by side", SIDE_BY_SIDE, True), ("two lines", TWO_LINES, True), ("no headings", bare, True),
                              ("a form", "Total emoluments        1,107,000.00\nTax withheld  71,401.00\n", False),
                              ("nothing", "Nothing here at all\n", False)):
      with self.subTest(name): self.assertEqual(is_statement(text), holds)

  def test_a_statement_that_reads_whole_loses_no_amount(self):
    for name, text in (("side by side", SIDE_BY_SIDE), ("two lines", TWO_LINES), ("second page", SECOND_PAGE)):
      with self.subTest(name): self.assertEqual(dropped(text), {})

  def test_an_amount_in_a_column_that_explains_nothing_is_counted(self):
    self.assertEqual(dropped(BOTH_WAYS), {1: 2})

  def test_a_cover_page_does_not_stop_the_statement_being_read(self):
    cover = "Your statement\nAccount number 0012345678\nOpening balance 1,000.00\nClosing balance 4,312.50\n\f" + SIDE_BY_SIDE
    self.assertEqual(len(entries(cover)), len(entries(SIDE_BY_SIDE)))

if __name__ == "__main__": unittest.main()
