import json, unittest
from decimal import Decimal
from it01.law import AssetKind, Source
from it01.tax import Asset, Business, Facts, Figure, assess, chargeable_income, from_json, income_tax
from test.helpers import ROOT

CASES = json.loads((ROOT/"test"/"cases"/"calculator.json").read_text(), parse_float=Decimal)
OUTPUTS = ("chargeable_income", "income_tax", "fair_share", "total")

def facts(c:dict) -> Facts: return from_json(Facts, {k: v for k, v in c.items() if k not in OUTPUTS + ("case",)})
def fig(figs:tuple[Figure, ...], rule:str) -> Figure: return next(x for x in figs if x.rule == rule)

def amounts(kw:dict) -> dict: return {k: v if isinstance(v, (Business, tuple)) else Decimal(v) for k, v in kw.items()}
def biz(**kw) -> Business: return Business(**amounts(kw))

def net(**kw) -> tuple[Decimal, Decimal]:
  figs = assess(Facts(True, **amounts(kw)))
  return fig(figs, "chargeable income").amt, fig(figs, "losses carried forward").amt

def ci(dependants:int=0, **kw) -> Decimal: return chargeable_income(Facts(True, dependants, **amounts(kw))).amt

class TestIncomeTax(unittest.TestCase):
  def test_calculator_cases(self):
    for c in CASES:
      with self.subTest(c["case"]): self.assertIn(c["income_tax"] - income_tax(Decimal(c["chargeable_income"])).amt, (0, 1))

  def test_drops_the_fraction_in_each_band(self):
    for amt, tax in ((500005, 0), (500019, 1), (999999, 49999), (1000009, 50001)):
      with self.subTest(amt): self.assertEqual(income_tax(Decimal(amt)).amt, tax)

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
    self.assertEqual(ci(salary=3000000, business=biz(gross_income=1000000), housing_loan_interest=100000), 3900000)
    self.assertEqual(ci(salary=3000000, business=biz(gross_income=1000001), housing_loan_interest=100000), 4000001)

  def test_cites_reliefs_only_for_a_resident(self):
    relief = Source("ita", "Third Schedule Part I", 280)
    self.assertIn(relief, chargeable_income(Facts(True)).src)
    self.assertNotIn(relief, chargeable_income(Facts(False)).src)

  def test_fifth_dependant_never_counts(self): self.assertEqual(ci(salary=1000000, dependants=5), ci(salary=1000000, dependants=4))

  def test_refuses_invalid_facts(self):
    bad = ({"salary": Decimal(-1)}, {"dependants": -1}, {"resident_dividends": Decimal("NaN")}, {"salary": -1}, {"salary": Decimal("1e15")},
           {"salary": Decimal("0.001")}, {"salary": Decimal("1.4999999999999999999999999999")})
    for kw in bad:
      with self.subTest(kw), self.assertRaises(ValueError): Facts(True, **kw)

class TestBusinessIncome(unittest.TestCase):
  def test_profit_adds_to_salary(self):
    self.assertEqual(net(salary=1200000, business=biz(gross_income=300000, other_expenses=100000)), (1400000, 0))

  def test_loss_never_reduces_salary(self):
    self.assertEqual(net(salary=1200000, business=biz(gross_income=100000, other_expenses=300000)), (1200000, 200000))

  def test_loss_reduces_other_income(self):
    self.assertEqual(net(salary=1200000, other_income=150000, business=biz(gross_income=100000, other_expenses=300000)), (1200000, 50000))

  def test_brought_forward_loss_reduces_profit(self):
    got = net(salary=1000000, business=biz(gross_income=400000, other_expenses=100000), losses_brought_forward=500000)
    self.assertEqual(got, (1000000, 200000))

  def test_cites_the_loss_rules(self): self.assertEqual(fig(assess(Facts(True)), "losses carried forward").src, (Source("ita", "s.20", 40),))

def asset(kind:str, cost:str, before:str="0") -> Asset: return Asset(AssetKind[kind.upper()], Decimal(cost), Decimal(before))

class TestAccounts(unittest.TestCase):
  LINES = biz(gross_income=1000000, cost_of_sales=300000, other_income=50000, wages=100000, rent=60000, depreciation=20000,
              entertainment_gifts_and_donations=10000, income_not_in_accounts=1000, non_allowable_expenses=5000, assets=(asset("computer", "80000"),))

  def test_follows_the_return_lines(self):
    figs = assess(Facts(True, business=self.LINES))
    rules = ("gross profit", "net profit per accounts", "non-allowable expenses", "annual allowance on computer", "net income from business")
    self.assertEqual([fig(figs, r).amt for r in rules], [700000, 560000, 35000, 40000, 556000])

  def test_adds_back_depreciation_and_entertainment(self):
    figs = assess(Facts(True, business=biz(gross_income=100000, depreciation=20000, entertainment_gifts_and_donations=10000)))
    self.assertEqual(fig(figs, "net income from business").amt, 100000)

  def test_net_income_cites_the_disallowed_items(self):
    self.assertIn(Source("ita", "s.26(1)", 46), fig(assess(Facts(True, business=self.LINES)), "net income from business").src)

  def test_no_business_figures_without_a_business(self):
    self.assertNotIn("gross profit", [x.rule for x in assess(Facts(True, salary=Decimal(1000000)))])

class TestAnnualAllowance(unittest.TestCase):
  def test_rates(self):
    cases = [("computer", "80000", "0", 40000), ("computer", "70001", "0", 35000), ("computer", "50000", "0", 50000),
             ("furniture", "1000000", "200000", 160000), ("other_plant", "60000", "0", 60000), ("electronic_equipment", "500000", "0", 500000),
             ("green_technology", "50000", "0", 50000), ("green_technology", "100000", "0", 50000), ("commercial_premises", "1000000", "0", 50000),
             ("commercial_premises", "1000000", "980000", 20000), ("other_capital_item", "40000", "0", 2000)]
    for kind, cost, before, amt in cases:
      with self.subTest(kind=kind, cost=cost, before=before): self.assertEqual(asset(kind, cost, before).allowance, amt)

  def test_next_year_reads_this_year(self):
    first = asset("other_plant", "100000.01")
    self.assertEqual((first.allowance, asset("other_plant", "100000.01", str(first.allowance)).allowance), (35000, 22750))

  def test_reduces_business_income(self):
    f = Facts(True, salary=Decimal(1200000), business=biz(gross_income=300000, other_expenses=100000, assets=(asset("computer", "80000"),)))
    figs = assess(f)
    self.assertEqual((fig(figs, "chargeable income").amt, fig(figs, "annual allowance on computer").amt), (1360000, 40000))

  def test_allowance_can_make_a_loss(self):
    figs = assess(Facts(True, salary=Decimal(1200000), business=biz(gross_income=20000, assets=(asset("computer", "100000"),))))
    self.assertEqual((fig(figs, "chargeable income").amt, fig(figs, "losses carried forward").amt), (1200000, 30000))

  def test_refuses_bad_assets(self):
    for kind, cost, before in (("computer", "100", "101"), ("motor_vehicle", "3000001", "0"), ("computer", "-1", "0")):
      with self.subTest(kind=kind, cost=cost), self.assertRaises(ValueError): asset(kind, cost, before)

  def test_cites_the_schedule(self):
    figs = assess(Facts(True, business=biz(assets=(asset("computer", "1"),))))
    self.assertIn(Source("regs", "Fourth Schedule", 46), fig(figs, "annual allowance on computer").src)

class TestAssess(unittest.TestCase):
  def test_calculator_cases(self):
    for c in CASES:
      with self.subTest(c["case"]):
        income, tax, share, total, *_ = (fig.amt for fig in assess(facts(c)))
        self.assertEqual((income, share), (c["chargeable_income"], c["fair_share"]))
        self.assertIn(c["income_tax"] - tax, (0, 1))
        self.assertEqual(c["total"] - total, c["income_tax"] - tax)

  def test_employers_guide_illustration(self):
    f = Facts(True, 1, salary=Decimal(20200000), resident_dividends=Decimal(1000000))
    self.assertEqual([fig.amt for fig in assess(f)], [20090000, 3868000, 1363500, 5231500, 5231500, 0])

  def test_largest_amounts_are_exact(self):
    m = Decimal(10**15 - 1)
    f = Facts(False, salary=m, taxable_transport_allowance=m, performance_bonus=m, statutory_bonus=m, other_income=m)
    self.assertEqual([fig.amt for fig in assess(f)], [4999999999999995, 999999999849999, 749999998199999, 1749999998049998, 1749999998049998, 0])

  def test_balance_credits_tax_already_paid(self):
    for paye, balance in ((40000, 18000), (60000, -2000)):
      with self.subTest(paye):
        f = Facts(True, 1, salary=Decimal(1200000), paye_withheld=Decimal(paye), tax_deducted_at_source=Decimal(5000),
                  quarterly_tax_paid=Decimal(5000))
        self.assertEqual(assess(f)[4].amt, balance)

  def test_balance_cites_the_credits(self):
    self.assertLessEqual({"s.93(1)", "s.103", "s.111(2)", "s.111G", "s.152(1)"}, {s.section for s in assess(Facts(True))[4].src})

  def test_fair_share_cites_its_sections(self):
    self.assertEqual(assess(Facts(True))[2].src, (Source("ita", "s.16B", 35), Source("ita", "s.16C", 37)))

if __name__ == "__main__": unittest.main()
