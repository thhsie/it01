import unittest
from it01.form import Form, ending, is_titled, wanted

class TestForm(unittest.TestCase):
  def test_the_shipped_form_knows_its_title(self):
    self.assertTrue(is_titled(wanted(), "Employer copy\nStatement of emoluments\nSalary 1,200.00"))

  def test_a_title_split_across_spaces_still_reads(self):
    self.assertTrue(is_titled(wanted(), "Statement  of\nEmoluments"))

  def test_a_payslip_does_not_carry_the_title(self):
    self.assertFalse(is_titled(wanted(), "PAY STATEMENT\nPERIOD: June 2026\nNet Pay 90 552,00"))

  def test_a_form_with_no_title_reads_any_document(self):
    self.assertTrue(is_titled(Form("soe", (("total", "the total"),)), "PAY STATEMENT"))

  def test_the_shipped_form_reads_the_last_month_of_its_year(self):
    self.assertEqual(ending(wanted(), "for the Income Year ended 30 June 2026"), "2026-06")

  def test_a_month_that_is_not_a_month_gives_no_year_end(self):
    self.assertIsNone(ending(wanted(), "income year ended 30 Juno 2026"))

if __name__ == "__main__": unittest.main()
