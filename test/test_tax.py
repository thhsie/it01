import json, unittest
from decimal import Decimal
from it01.law import Source
from it01.tax import Facts, assess, chargeable_income, income_tax
from test.helpers import ROOT

CASES = json.loads((ROOT/"test"/"cases"/"calculator.json").read_text(), parse_float=Decimal)
AMOUNTS = ("salary", "taxable_transport_allowance", "performance_bonus", "statutory_bonus", "other_income", "resident_dividends",
           "housing_loan_interest", "medical_insurance", "other_reliefs")
OUTPUTS = ("chargeable_income", "income_tax", "fair_share", "total")

def facts(c:dict) -> Facts: return Facts(c["resident"], c["dependants"], **{k: Decimal(c[k]) for k in AMOUNTS})
def ci(dependants:int=0, **kw) -> Decimal: return chargeable_income(Facts(True, dependants, **{k: Decimal(v) for k, v in kw.items()})).amt

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

class TestChargeableIncome(unittest.TestCase):
  def test_calculator_cases(self):
    for c in CASES:
      with self.subTest(c["case"]): self.assertEqual(chargeable_income(facts(c)).amt, c["chargeable_income"])

  def test_medical_relief_is_capped(self):
    self.assertEqual(ci(salary=1000000, medical_insurance=40000), 975000)
    self.assertEqual(ci(salary=1000000, medical_insurance=200000, dependants=4), 1000000 - 355000 - 110000)

  def test_interest_relief_barred_above_four_million(self):
    self.assertEqual(ci(salary=3000000, resident_dividends=1000000, housing_loan_interest=100000), 2900000)
    self.assertEqual(ci(salary=3000000, resident_dividends=1000001, housing_loan_interest=100000), 3000000)

  def test_cites_reliefs_only_for_a_resident(self):
    relief = Source("ita", "Third Schedule Part I", 280)
    self.assertIn(relief, chargeable_income(Facts(True)).src)
    self.assertNotIn(relief, chargeable_income(Facts(False)).src)

  def test_fifth_dependant_never_counts(self): self.assertEqual(ci(salary=1000000, dependants=5), ci(salary=1000000, dependants=4))

  def test_refuses_invalid_facts(self):
    for kw in ({"salary": Decimal(-1)}, {"dependants": -1}, {"resident_dividends": Decimal("NaN")}, {"salary": -1}):
      with self.subTest(kw), self.assertRaises(ValueError): Facts(True, **kw)

class TestAssess(unittest.TestCase):
  def test_calculator_cases(self):
    for c in CASES:
      with self.subTest(c["case"]): self.assertEqual([fig.amt for fig in assess(facts(c))], [c[k] for k in OUTPUTS])

  def test_employers_guide_illustration(self):
    f = Facts(True, 1, salary=Decimal(20200000), resident_dividends=Decimal(1000000))
    self.assertEqual([fig.amt for fig in assess(f)], [20090000, 3868000, 1363500, 5231500])

  def test_fair_share_cites_its_sections(self):
    self.assertEqual(assess(Facts(True))[2].src, (Source("ita", "s.16B", 35), Source("ita", "s.16C", 37)))

if __name__ == "__main__": unittest.main()
