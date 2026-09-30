import unittest
from it01.form import Form, is_titled, wanted

class TestForm(unittest.TestCase):
  def test_the_shipped_form_knows_its_title(self):
    self.assertTrue(is_titled(wanted(), "Employer copy\nStatement of emoluments\nSalary 1,200.00"))

  def test_a_title_split_across_spaces_still_reads(self):
    self.assertTrue(is_titled(wanted(), "Statement  of\nEmoluments"))

  def test_a_payslip_does_not_carry_the_title(self):
    self.assertFalse(is_titled(wanted(), "PAY STATEMENT\nPERIOD: June 2026\nNet Pay 90 552,00"))

  def test_a_form_with_no_title_reads_any_document(self):
    self.assertTrue(is_titled(Form("soe", (("total", "the total"),)), "PAY STATEMENT"))

if __name__ == "__main__": unittest.main()
