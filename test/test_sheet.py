import unittest
from dataclasses import fields
from decimal import Decimal
from it01.helpers import data
from it01.law import Addition, Period
from it01.sheet import sheet, untyped
from it01.tax import Business, Dependant, Facts, Letting, Student, assess

FULL = Facts(True, 2, salary=Decimal(1000000), paye_withheld=Decimal(50000), rent=Decimal(120000), letting=Letting(repairs=Decimal(20000)),
             medical_insurance=(Decimal(20000), Decimal(0), Decimal(15000)), dependant_income=(Dependant(Decimal(50000), Decimal(20000)),),
             additional_deduction=Addition.DISABLED, business=Business(gross_income=Decimal(200000)), tax_deducted_at_source=Decimal(3000))

class TestSheet(unittest.TestCase):
  def test_every_fact_is_on_the_sheet_or_named_as_not(self):
    table = data("portal")
    placed = {spec.partition(":")[2].split(".")[0] for _, spec in table["fields"]} | {"dependant_income"}
    for one in fields(Facts):
      with self.subTest(one.name): self.assertIn(one.name, placed | set(table["covered"]) | set(table["untyped"]))

  def test_every_figure_named_is_one_the_engine_gives(self):
    rules = {fig.rule for fig in assess(FULL)}
    for field, spec in data("portal")["fields"]:
      kind, _, name = spec.partition(":")
      if kind == "figure":
        with self.subTest(field): self.assertIn(name, rules)

  def test_a_case_gives_its_fields_in_the_return_order(self):
    got = dict(pairs := sheet(FULL))
    self.assertEqual([k for k, _ in pairs][:3], ["CHKTXTNODEPENDENT", "B_A_GROSINC", "B_A_GRENT"])
    self.assertEqual((got["B_A_GRENT"], got["B_A_RENTREP_MTAN"], got["B_D_ENEXINC1"]), ("120000", "20000", "1000000"))
    self.assertEqual((got["B_A_NETEXINC"], got["B_A_EXEINC"]), ("50000", "20000"))
    self.assertEqual((got["B_D_PREMIUM1"], got["B_D_PREMIUM3"], got["incThresholdOpt"], got["B_A_RET_DIS"]), ("20000", "15000", "C", "D"))
    self.assertEqual((got["B_G_TN_TOTAL1"], got["B_A_TOTOITDS"]), ("3000", "3000"))
    self.assertNotIn("B_D_PREMIUM2", got)
    self.assertEqual(got["B_A_BALTAX"], str(next(x.amt for x in assess(FULL) if x.rule == "balance of tax")))

  def test_an_amount_with_cents_is_given_whole_as_the_return_keeps_it(self):
    held = Facts(True, salary=Decimal("1106870.50"), medical_insurance=(Decimal("20000.99"),), business=Business(gross_income=Decimal("250000.75")))
    got = dict(sheet(held))
    self.assertEqual((got["B_D_ENEXINC1"], got["B_D_PREMIUM1"], got["B_A_GROSINC"]), ("1106870", "20000", "250000"))

  def test_the_totals_follow_the_whole_amounts_typed(self):
    got = dict(sheet(Facts(True, salary=Decimal("1106870.50"), tax_deducted_at_source=Decimal("10000.60"))))
    typed = dict(sheet(Facts(True, salary=Decimal(1106870), tax_deducted_at_source=Decimal(10000))))
    self.assertEqual((got["B_A_CHGINC"], got["B_A_BALTAX"]), (typed["B_A_CHGINC"], typed["B_A_BALTAX"]))

  def test_checks_stay_even_at_nothing(self):
    got = dict(sheet(Facts(True)))
    self.assertEqual((got["B_A_CHGINC"], got["B_A_RESIDENT"]), ("0", "Yes"))
    self.assertNotIn("B_A_GRENT", got)

  def test_the_dependant_count_and_category_follow_the_return(self):
    self.assertEqual(dict(sheet(Facts(True, 6)))["CHKTXTNODEPENDENT"], "4")
    self.assertNotIn("incThresholdOpt", dict(sheet(Facts(False))))

  def test_a_quarter_is_refused(self):
    with self.assertRaisesRegex(ValueError, "the return is for a year, not for a quarter"): sheet(Facts(True, rent=Decimal(1), period=Period.QUARTER))

  def test_facts_with_no_field_are_named(self):
    f = Facts(True, 1, students=(Student(True, True, Decimal(0), 1),), other_income=Decimal(5))
    self.assertEqual([note.split(" ")[0] for note in untyped(f)], ["other_income", "students"])
    self.assertEqual(untyped(Facts(True)), [])

if __name__ == "__main__": unittest.main()
