import json, unittest
from decimal import Decimal
from it01.law import Source
from it01.tax import income_tax
from test.helpers import ROOT

CASES = json.loads((ROOT/"test"/"cases"/"calculator.json").read_text(), parse_float=Decimal)

class TestIncomeTax(unittest.TestCase):
  def test_calculator_cases(self):
    for c in CASES:
      with self.subTest(c["case"]): self.assertEqual(income_tax(Decimal(c["chargeable_income"])).amt, c["income_tax"])

  def test_names_rule_and_sources(self):
    fig = income_tax(Decimal(1))
    self.assertEqual((fig.rule, fig.src), ("income tax", (Source("ita", "s.4", 26), Source("ita", "First Schedule Part I", 262))))

  def test_refuses_invalid_income(self):
    for bad in ("-1", "0.5", "Infinity", "NaN"):
      with self.subTest(bad), self.assertRaises(ValueError): income_tax(Decimal(bad))

if __name__ == "__main__": unittest.main()
