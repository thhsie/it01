import json, unittest
from decimal import Decimal
from it01.helpers import instruction
from it01.read import Proposal, proposals
from it01.tax import AMOUNTS

PAY = "Total emoluments        1,107,000.00"
TAX = "Tax withheld               71,401.00"
PERIOD = "Period 01/07/2024 to 30/06/2025"
STAFF = "Payslip for employee 11070001"
PENSION = "Pension contribution       55,000.00"
ROUND = "Rounded total              1,107,000"
TRAVEL = "Travelling allowance          66 870,00"
DOC = "\n".join(["STATEMENT OF EMOLUMENTS", PERIOD, STAFF, PAY, TAX, PENSION, ROUND, TRAVEL, ""])

def reply(fact:str="salary", amount:object="1,107,000.00", quote:str=PAY) -> str:
  return json.dumps([{"fact": fact, "amount": amount, "quote": quote}])

REFUSED = [
  (reply(quote="Total emoluments 9,999,999.00"), "not a line of the document"),
  (reply(quote="Total"), "not a line of the document"),
  (reply(fact="bonus_of_some_kind"), "unknown fact"),
  (reply(fact=None), "unknown fact"),
  (reply(amount="about a million"), "not an amount"),
  (reply(amount="1,2,3"), "not an amount"),
  (reply(amount="1E+9"), "not an amount"),
  (reply(amount="NaN"), "not an amount"),
  (reply(amount="-1107000.00"), "not an amount"),
  (reply(amount="1107000.000"), "not an amount"),
  (reply(fact="paye_withheld", amount="71,401.00"), "does not show"),
  (reply(amount="20.24", quote=PERIOD), "does not show"),
  (reply(amount="1107000", quote=STAFF), "does not show"),
  (reply(amount="5000", quote=PENSION), "does not show"),
  ("Here are the figures I found.", "did not answer with JSON"),
  ('{"fact": "salary"}', "must answer with a JSON list"),
  ("[1]", "must be a JSON object"),
]

class TestRead(unittest.TestCase):
  def test_proposal_carries_the_line_it_came_from(self):
    self.assertEqual(proposals(DOC, reply()), (Proposal("salary", Decimal("1107000.00"), PAY),))

  def test_amount_may_be_a_number(self):
    self.assertEqual(proposals(DOC, reply(fact="paye_withheld", amount=71401, quote=TAX))[0].amt, Decimal(71401))

  def test_line_without_decimals_shows_the_same_figure(self):
    self.assertEqual(proposals(DOC, reply(amount="1107000.00", quote=ROUND))[0].amt, Decimal("1107000.00"))

  def test_an_amount_written_with_a_space_and_a_comma_is_read(self):
    said = reply(fact="taxable_transport_allowance", amount="66 870,00", quote=TRAVEL)
    self.assertEqual(proposals(DOC, said)[0].amt, Decimal("66870.00"))

  def test_refuses_what_the_document_does_not_support(self):
    for answer, msg in REFUSED:
      with self.subTest(answer): self.assertRaisesRegex(ValueError, msg, proposals, DOC, answer)

  def test_empty_list_proposes_nothing(self): self.assertEqual(proposals(DOC, "[]"), ())

  def test_the_instruction_names_every_fact(self):
    asked = instruction("reading").format(facts=", ".join(AMOUNTS))
    for fact in AMOUNTS: self.assertIn(fact, asked)

if __name__ == "__main__": unittest.main()
