import json, unittest
from decimal import Decimal
from it01.law import DEPENDANTS, HEADS, Addition, AssetKind, Period, Source
from it01.tax import (AMOUNTS, RECORDS, Asset, Business, Dependant, Facts, Farming, Figure, Lending, Letting, Student, Tuition, amount,
                       assess, chargeable_income, figures, from_json, income_tax)
from test.helpers import ROOT

CASES = json.loads((ROOT/"test"/"cases"/"calculator.json").read_text(), parse_float=Decimal)
OUTPUTS = ("chargeable_income", "income_tax", "fair_share", "total")

def facts(c:dict) -> Facts: return from_json(Facts, {k: v for k, v in c.items() if k not in OUTPUTS + ("case",)})
def fig(figs:tuple[Figure, ...], rule:str) -> Figure: return next(x for x in figs if x.rule == rule)

def amounts(kw:dict) -> dict: return {k: v if isinstance(v, (*RECORDS, tuple, Addition)) else Decimal(v) for k, v in kw.items()}
def biz(**kw) -> Business: return Business(**amounts(kw))

def net(**kw) -> tuple[Decimal, Decimal]:
  figs = assess(Facts(True, **amounts(kw)))
  return fig(figs, "chargeable income").amt, fig(figs, "losses carried forward").amt

def ci(dependants:int=0, **kw) -> Decimal: return chargeable_income(Facts(True, dependants, **amounts(kw))).amt

class TestQuarter(unittest.TestCase):
  def test_quarter_bands(self):
    for amt, tax in ((Decimal(125000), 0), (Decimal(250000), 12500), (Decimal(400000), 42500),
                     (Decimal(125019), 1), (Decimal(250019), 12503)):
      with self.subTest(amt): self.assertEqual(income_tax(amt, Period.QUARTER).amt, tax)

  def test_quarter_refuses_reliefs_of_the_year(self):
    for kw in ({"school_fees": (Decimal(1),)}, {"electronic_donations": Decimal(1)}, {"additional_deduction": Addition.DISABLED},
               {"students": (Student(True, True, Decimal(0), 1),)}):
      with self.subTest(kw), self.assertRaisesRegex(ValueError, "a quarter does not take"): Facts(True, 1, period=Period.QUARTER, **kw)

  def test_quarter_reliefs(self):
    held = Facts(True, 1, rent=Decimal(400000), period=Period.QUARTER)
    self.assertEqual(chargeable_income(held).amt, Decimal(372500))

  def test_quarter_sources(self):
    for resident in (True, False):
      with self.subTest(resident):
        figs = assess(Facts(resident, rent=Decimal(400000), period=Period.QUARTER))
        self.assertIn(Source("ita", "s.107(2)", 122), fig(figs, "chargeable income").src)
        self.assertIn(Source("cps", "9. Calculation of Tax", 6), fig(figs, "income tax").src)

  def test_quarter_figures(self):
    figs = assess(Facts(True, rent=Decimal(400000), period=Period.QUARTER))
    self.assertEqual([x.rule for x in figs], ["chargeable income", "income tax", "tax already paid", "balance of tax", "losses carried forward"])

  def test_quarter_credit(self):
    held = Facts(True, rent=Decimal(400000), tax_deducted_at_source=Decimal(1000), period=Period.QUARTER)
    self.assertEqual(fig(assess(held), "balance of tax").amt, Decimal(41500))

  def test_quarter_refuses_the_year(self):
    for name in AMOUNTS:
      if name in ("rent", "losses_brought_forward", "tax_deducted_at_source"): continue
      with self.subTest(name), self.assertRaisesRegex(ValueError, f"quarter does not take \\['{name}'\\]"):
        Facts(True, period=Period.QUARTER, **{name: Decimal(1)})

  def test_quarter_takes_a_quarter_of_the_allowance(self):
    held = biz(gross_income=900000, assets=(Asset(AssetKind.COMPUTER, Decimal(80000)),))
    figs = assess(Facts(True, business=held, period=Period.QUARTER))
    self.assertEqual(fig(figs, "a quarter of the annual allowance on computer").amt, Decimal(10000))
    self.assertEqual(fig(figs, "net income from business").amt, Decimal(890000))

  def test_quarter_shows_the_business_working(self):
    figs = assess(Facts(True, business=biz(gross_income=900000), period=Period.QUARTER))
    self.assertEqual([x.rule for x in figs][-4:],
                     ["gross profit", "net profit per accounts", "non-allowable expenses", "net income from business"])

  def test_quarter_allowance_keeps_its_cents(self):
    self.assertEqual(asset("computer", "50000").allowance(Decimal("0.25")), Decimal("12500.00"))

  def test_quarter_allowance_names_the_guidance(self):
    held = biz(assets=(Asset(AssetKind.COMPUTER, Decimal(80000)),))
    figs = assess(Facts(True, business=held, period=Period.QUARTER))
    self.assertIn(Source("cps", "7. Annual allowance", 3), fig(figs, "a quarter of the annual allowance on computer").src)

class TestIncomeTax(unittest.TestCase):
  def test_calculator_cases(self):
    for c in CASES:
      with self.subTest(c["case"]): self.assertIn(c["income_tax"] - income_tax(Decimal(c["chargeable_income"]), Period.YEAR).amt, (0, 1))

  def test_drops_the_fraction_in_each_band(self):
    for amt, tax in ((500005, 0), (500019, 1), (999999, 49999), (1000009, 50001)):
      with self.subTest(amt): self.assertEqual(income_tax(Decimal(amt), Period.YEAR).amt, tax)

  def test_names_rule_and_sources(self):
    fig = income_tax(Decimal(1), Period.YEAR)
    self.assertEqual((fig.rule, fig.src), ("income tax", (Source("ita", "s.4", 26), Source("ita", "First Schedule Part I", 262))))

  def test_refuses_invalid_income(self):
    for bad in ("-1", "0.5", "Infinity", "NaN"):
      with self.subTest(bad), self.assertRaises(ValueError): income_tax(Decimal(bad), Period.YEAR)

class TestChargeableIncome(unittest.TestCase):
  def test_calculator_cases(self):
    for c in CASES:
      with self.subTest(c["case"]): self.assertEqual(chargeable_income(facts(c)).amt, c["chargeable_income"])

  def test_medical_relief_is_capped_per_person(self):
    for dependants, paid, relief in ((0, (40000,), 25000), (4, (50000,) * 5, 110000), (2, (40000,), 25000), (2, (0, 0, 30000), 20000)):
      with self.subTest(paid):
        self.assertEqual(ci(dependants, salary=1000000, medical_insurance=tuple(Decimal(x) for x in paid)), 1000000 - DEPENDANTS[dependants] - relief)

  def test_medical_relief_names_no_more_people_than_the_case(self):
    with self.assertRaisesRegex(ValueError, "medical_insurance names 3 people, at most 2 can be insured"):
      Facts(True, 1, medical_insurance=(Decimal(1), Decimal(1), Decimal(1)))

  def test_capped_reliefs(self):
    for kw, relief in (({"school_fees": (Decimal(70000), Decimal(30000))}, 90000), ({"electronic_donations": 150000}, 100000),
                       ({"pension_contributions": 60000}, 50000), ({"carer_wages": 40000}, 30000), ({"carer_wages": 20000}, 20000)):
      with self.subTest(kw): self.assertEqual(ci(2, salary=1000000, **kw), 1000000 - DEPENDANTS[2] - relief)

  def test_tertiary_deduction_follows_the_schedule(self):
    for student, relief in ((Student(True, True, Decimal(0), 1), 500000), (Student(False, True, Decimal(30000), 1), 0),
                            (Student(False, True, Decimal(34800), 3), 500000), (Student(False, False, Decimal(0), 1), 500000),
                            (Student(True, False, Decimal(0), 7), 0)):
      with self.subTest(student): self.assertEqual(ci(1, salary=2000000, students=(student,)), 2000000 - DEPENDANTS[1] - relief)

  def test_student_refuses_a_year_before_the_first(self):
    with self.assertRaisesRegex(ValueError, "invalid year 0"): Student(True, True, Decimal(0), 0)

  def test_additional_deduction_for_a_retired_or_disabled_person(self):
    for addition, salary, relief in ((Addition.RETIRED, 40000, 50000), (Addition.RETIRED, 60000, 0), (Addition.DISABLED, 1000000, 50000)):
      with self.subTest(addition, salary=salary):
        self.assertEqual(ci(salary=salary, other_income=1000000, additional_deduction=addition), salary + 1000000 - relief)
    for held in ({"business": biz(gross_income=1000)}, {"farming": Farming(Decimal(1000))}, {"tuition": Tuition(Decimal(1000))},
                 {"lending": Lending(Decimal(5000))}):
      with self.subTest(held): self.assertEqual(ci(salary=40000, additional_deduction=Addition.RETIRED, **held), 41000)

  def test_reliefs_name_no_more_children_than_the_case(self):
    student = Student(True, True, Decimal(0), 1)
    for kw in ({"school_fees": (Decimal(1), Decimal(1))}, {"students": (student,) * 2}, {"school_fees": (Decimal(1),), "students": (student,)}):
      with self.subTest(kw), self.assertRaisesRegex(ValueError, "school_fees and students name 2 children, more than the 1 dependants"):
        Facts(True, 1, **kw)
    with self.assertRaisesRegex(ValueError, "students names 5 children, at most 4 can be claimed"): Facts(True, 5, students=(student,) * 5)

  def test_reliefs_read_from_json(self):
    raw = {"resident": True, "dependants": 2, "additional_deduction": "disabled", "school_fees": [70000],
           "dependant_income": [{"income": 5000}],
           "students": [{"abroad": True, "undergraduate": True, "tuition": 0, "year": 2}]}
    self.assertEqual(from_json(Facts, raw), Facts(True, 2, additional_deduction=Addition.DISABLED, school_fees=(Decimal(70000),),
                                                  dependant_income=(Dependant(Decimal(5000)),),
                                                  students=(Student(True, True, Decimal(0), 2),)))

  def test_interest_relief_barred_above_four_million(self):
    self.assertEqual(ci(salary=3000000, resident_dividends=1000000, housing_loan_interest=100000), 2900000)
    self.assertEqual(ci(salary=3000000, resident_dividends=1000001, housing_loan_interest=100000), 3000000)
    self.assertEqual(ci(salary=3000000, business=biz(gross_income=1000000), housing_loan_interest=100000), 3900000)
    self.assertEqual(ci(salary=3000000, business=biz(gross_income=1000001), housing_loan_interest=100000), 4000001)

  def test_interest_bar_counts_exempt_interest_and_dividends(self):
    for kw in ({"exempt_interest": 1000001}, {"global_business_dividends": 600000, "exempt_interest": 400001}):
      with self.subTest(kw): self.assertEqual(ci(salary=3000000, housing_loan_interest=100000, **kw), 3000000)
    self.assertEqual(ci(salary=3000000, exempt_interest=1000000, housing_loan_interest=100000), 2900000)

  def test_interest_relief_barred_by_the_spouse(self):
    f = Facts(True, salary=Decimal(1000000), housing_loan_interest=Decimal(100000), spouse_above_interest_bar=True)
    self.assertEqual(chargeable_income(f).amt, 1000000)

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

class TestIncomeHeads(unittest.TestCase):
  def test_heads_add_to_other_income_and_take_losses(self):
    got = net(salary=1000000, basic_retirement_pension=100000, taxable_interest=20000, royalty=5000, foreign_dividend=15000,
              business=biz(gross_income=10000, other_expenses=50000))
    self.assertEqual(got, (1000000 + 140000 - 40000, 0))

  def test_every_head_adds_to_income(self):
    for name in HEADS:
      with self.subTest(name): self.assertEqual(ci(**{name: 1000001}), 1000001)

  def test_heads_cite_what_makes_them_income(self):
    src = fig(assess(Facts(True, state_pension=Decimal(1), foreign_interest=Decimal(1))), "chargeable income").src
    self.assertTrue({Source("ita", "s.10(1)(d)", 31), Source("ita", "s.5(3)", 28)} <= set(src))
    self.assertNotIn(Source("ita", "s.10(1)(e)", 31), src)

  def test_income_from_abroad_needs_residence(self):
    with self.assertRaisesRegex(ValueError, r"a non-resident cannot have income from abroad \['foreign_rent'\]"):
      Facts(False, foreign_rent=Decimal(1))

  def test_quarter_refuses_the_heads(self):
    with self.assertRaisesRegex(ValueError, "a quarter does not take"): Facts(True, taxable_interest=Decimal(1), period=Period.QUARTER)

class TestDutyExpenses(unittest.TestCase):
  def test_duty_expenses_come_off_emoluments(self):
    for duty, emoluments in ((120000, 1107000), (2000000, 0)):
      with self.subTest(duty): self.assertEqual(net(salary=1227000, duty_expenses=duty, rent=10000), (emoluments + 10000, 0))

  def test_retired_test_reads_emoluments_before_duty_expenses(self):
    self.assertEqual(ci(salary=60000, duty_expenses=20000, additional_deduction=Addition.RETIRED), 40000)

  def test_duty_expenses_cite_section_17(self):
    self.assertIn(Source("ita", "s.17(1)", 37), chargeable_income(Facts(True, salary=Decimal(1), duty_expenses=Decimal(1))).src)

class TestDependantIncome(unittest.TestCase):
  def test_income_of_a_dependant_counts_as_yours(self):
    held = (Dependant(Decimal(100000), Decimal(20000), Decimal(30000)), Dependant(Decimal(50000)))
    self.assertEqual(ci(2, salary=1000000, dependant_income=held), 1000000 + 30000 + 50000 + 50000 - DEPENDANTS[2])

  def test_only_other_income_of_a_dependant_takes_losses(self):
    held = Facts(True, 1, salary=Decimal(1000000), dependant_income=(Dependant(Decimal(60000), emoluments=Decimal(40000)),),
                 business=biz(gross_income=0, other_expenses=50000))
    self.assertEqual(fig(assess(held), "losses carried forward").amt, 30000)
    self.assertEqual(chargeable_income(held).amt, 1040000 - DEPENDANTS[1])

  def test_a_dependant_above_the_limit_cannot_be_claimed(self):
    with self.assertRaisesRegex(ValueError, "dependant 2 has 80,001 of income, above 80,000, so cannot be claimed"):
      Facts(True, 2, dependant_income=(Dependant(Decimal(0)), Dependant(Decimal(80001))))

  def test_a_non_resident_claims_no_dependant_income(self):
    with self.assertRaisesRegex(ValueError, "a non-resident cannot claim dependant_income"):
      Facts(False, 1, dependant_income=(Dependant(Decimal(1)),))

  def test_parts_cannot_exceed_the_income(self):
    with self.assertRaisesRegex(ValueError, "exempt income and emoluments exceed the income 10"): Dependant(Decimal(10), Decimal(6), Decimal(5))

  def test_no_more_incomes_than_dependants(self):
    with self.assertRaisesRegex(ValueError, "dependant_income names 2 dependants, at most 1 can have income"):
      Facts(True, 1, dependant_income=(Dependant(Decimal(0)),) * 2)

class TestNettedHeads(unittest.TestCase):
  def test_agriculture_profit_adds_and_loss_carries(self):
    self.assertEqual(net(salary=1000000, farming=Farming(**amounts(dict(gross_income=300000, labour=100000, fertilizers_and_pesticides=50000)))),
                     (1150000, 0))
    self.assertEqual(net(salary=1000000, taxable_interest=10000, farming=Farming(**amounts(dict(gross_income=10000, other_expenses=50000)))),
                     (1000000, 30000))

  def test_tuition_loss_counts_as_zero(self):
    for gross, expenses, added in ((200000, 50000, 150000), (20000, 50000, 0)):
      with self.subTest(gross): self.assertEqual(net(salary=1000000, tuition=Tuition(**amounts(dict(gross_income=gross, expenses=expenses)))),
                                                 (1000000 + added, 0))

  def test_peer_to_peer_interest_is_a_fifth_less_bad_debts(self):
    for interest, bad, taxable, carried in ((100000, 0, 20000, 0), (100000, 5000, 15000, 0), (100000, 30000, 0, 0), (10000, 25000, 0, 15000)):
      with self.subTest(interest=interest, bad=bad):
        figs = assess(Facts(True, lending=Lending(**amounts(dict(interest=interest, bad_debts=bad)))))
        self.assertEqual((fig(figs, "net interest from peer to peer lending").amt, fig(figs, "peer to peer bad debts carried forward").amt),
                         (taxable, carried))

  def test_netted_heads_read_from_json(self):
    raw = {"resident": True, "farming": {"gross_income": 1000}, "tuition": {"gross_income": 2000}, "lending": {"interest": 3000}}
    got = from_json(Facts, raw)
    self.assertEqual((got.farming.net, got.tuition.net, got.lending.taxable), (1000, 2000, 600))

class TestLetting(unittest.TestCase):
  def test_expenses_reduce_rent(self):
    held = Letting(Decimal(20000), Decimal(30000), Decimal(6000), Decimal(4000), (asset("commercial_premises", "1000000"),))
    self.assertEqual(net(salary=1000000, rent=300000, letting=held), (1000000 + 300000 - 60000 - 50000, 0))

  def test_loss_reduces_other_income_and_carries_forward(self):
    self.assertEqual(net(salary=1000000, rent=100000, other_income=50000, letting=Letting(repairs=Decimal(200000))), (1000000, 50000))

  def test_net_rent_is_shown_with_its_sources(self):
    got = fig(assess(Facts(True, rent=Decimal(300000), letting=Letting(interest=Decimal(1000)))), "net income from rent")
    self.assertEqual((got.amt, got.src[:4]), (299000, (Source("ita", "s.10(1)(c)", 31), Source("ita", "s.18(1)", 38),
                                                         Source("ita", "s.18(3)", 38), Source("ita", "s.19(1)", 40))))

  def test_quarter_refuses_letting_expenses(self):
    with self.assertRaisesRegex(ValueError, "a quarter does not take"):
      Facts(True, rent=Decimal(1), letting=Letting(repairs=Decimal(1)), period=Period.QUARTER)

  def test_letting_reads_from_json(self):
    raw = {"resident": True, "rent": 300000, "letting": {"repairs": 20000, "assets": [{"kind": "commercial_premises", "cost": 1000000}]}}
    self.assertEqual(from_json(Facts, raw).letting, Letting(repairs=Decimal(20000), assets=(asset("commercial_premises", "1000000"),)))

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
  def test_a_small_plant_keeps_its_cents(self):
    self.assertEqual(asset("computer", "59999.55").allowance(Decimal(1)), Decimal("59999.55"))

  def test_rates(self):
    cases = [("computer", "80000", "0", 40000), ("computer", "70001", "0", 35000), ("computer", "50000", "0", 50000),
             ("furniture", "1000000", "200000", 160000), ("other_plant", "60000", "0", 60000), ("electronic_equipment", "500000", "0", 500000),
             ("green_technology", "50000", "0", 50000), ("green_technology", "100000", "0", 50000), ("commercial_premises", "1000000", "0", 50000),
             ("commercial_premises", "1000000", "980000", 20000), ("other_capital_item", "40000", "0", 2000)]
    for kind, cost, before, amt in cases:
      with self.subTest(kind=kind, cost=cost, before=before): self.assertEqual(asset(kind, cost, before).allowance(Decimal(1)), amt)

  def test_next_year_reads_this_year(self):
    first = asset("other_plant", "100000.01")
    whole = first.allowance(Decimal(1))
    self.assertEqual((whole, asset("other_plant", "100000.01", str(whole)).allowance(Decimal(1))), (35000, 22750))

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

class TestWritten(unittest.TestCase):
  def test_an_amount_is_read_whichever_way_it_is_written(self):
    for written, want in (("1,107,000.00", "1107000.00"), ("1107000", "1107000"), ("666 870,00", "666870.00"),
                          ("1.234.567,89", "1234567.89"), ("2 700,00", "2700.00"), ("9448,5", "9448.5")):
      with self.subTest(written): self.assertEqual(amount(written), Decimal(want))

  def test_an_ambiguous_amount_is_refused(self):
    for written in ("1,2,3", "1 23,45", "666 870.00,25", "1107000.000", "666 870", "12345,678", "1,23,456.78"):
      with self.subTest(written): self.assertRaises(ValueError, amount, written)

  def test_every_amount_on_a_line_is_read(self):
    self.assertEqual(figures("Emoluments 666 870,00 tax withheld 31 116,00"), {Decimal("666870.00"), Decimal("31116.00")})

  def test_a_figure_inside_a_longer_run_of_digits_is_not_read(self):
    for line in ("12345,678", "1,23,456.78", "1.234"):
      with self.subTest(line): self.assertEqual(figures(line), set())

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
    self.assertEqual([fig.amt for fig in assess(f)], [20090000, 3868000, 1363500, 5231500, 0, 5231500, 0])

  def test_largest_amounts_are_exact(self):
    m = Decimal(10**15 - 1)
    f = Facts(False, salary=m, taxable_transport_allowance=m, performance_bonus=m, statutory_bonus=m, other_income=m)
    self.assertEqual([fig.amt for fig in assess(f)], [4999999999999995, 999999999849999, 749999998199999, 1749999998049998, 0, 1749999998049998, 0])

  def test_balance_credits_tax_already_paid(self):
    for paye, balance in ((40000, 18000), (60000, -2000)):
      with self.subTest(paye):
        f = Facts(True, 1, salary=Decimal(1200000), paye_withheld=Decimal(paye), tax_deducted_at_source=Decimal(5000),
                  quarterly_tax_paid=Decimal(5000))
        self.assertEqual(fig(assess(f), "balance of tax").amt, balance)

  def test_reports_tax_already_paid(self):
    held = Facts(True, salary=Decimal(1000000), paye_withheld=Decimal(30000), tax_deducted_at_source=Decimal(2000), quarterly_tax_paid=Decimal(5000))
    figs = assess(held)
    self.assertEqual(fig(figs, "tax already paid").amt, Decimal(37000))
    self.assertEqual(fig(figs, "balance of tax").amt, fig(figs, "total tax").amt - Decimal(37000))

  def test_balance_cites_the_credits(self):
    self.assertLessEqual({"s.93(1)", "s.103", "s.111(2)", "s.111G", "s.152(1)"}, {s.section for s in fig(assess(Facts(True)), "balance of tax").src})

  def test_fair_share_cites_its_sections(self):
    self.assertEqual(assess(Facts(True))[2].src, (Source("ita", "s.16B", 35), Source("ita", "s.16C", 37)))

if __name__ == "__main__": unittest.main()
