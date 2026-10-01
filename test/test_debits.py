import importlib.util, json, unittest
from decimal import Decimal
from unittest import mock
from it01.debits import spending, spent
from it01.helpers import data
from it01.kinds import paying, prompted
from it01.labels import totals

STATEMENT = """\
Date        Description                    Debit       Credit      Balance
01/07/2025  Opening balance                                       10,000.00
02/07/2025  SALARY JULY ACME LTD                     5,000.00     15,000.00
03/07/2025  Direct Debit RETIREMENT PLAN  1,000.00                14,000.00
04/07/2025  CARD PURCHASE GREEN MARKET      800.00                13,200.00
05/07/2025  ATM WITHDRAWAL                2,000.00                11,200.00
"""

PAID_IN = """\
Date        Description                    Debit       Credit      Balance
01/07/2025  Opening balance                                        1,000.00
02/07/2025  SALARY JULY ACME LTD                     5,000.00      6,000.00
03/07/2025  INTEREST PAID                               12.50      6,012.50
"""

PROMPT = prompted("paying", data("paying"))

def reply(*names:str) -> str: return json.dumps({str(n): name for n, name in enumerate(names, 1)})

class TestDebits(unittest.TestCase):
  def test_only_money_paid_out_is_labelled(self):
    self.assertEqual([amt for _, amt in spent(STATEMENT)], [Decimal("1000.00"), Decimal("800.00"), Decimal("2000.00")])

  def test_the_endpoint_labels_each_debit(self):
    with mock.patch("it01.labels.ask", return_value=reply("pension", "no_claim", "no_claim")) as said: found = spending(STATEMENT)
    self.assertEqual([d.kind for d in found], ["pension", "no_claim", "no_claim"])
    self.assertEqual(totals(found), {"pension": Decimal("1000.00"), "no_claim": Decimal("2800.00")})
    self.assertTrue(said.call_args.args[0].startswith(data("paying")["instruction"]))

  def test_a_statement_with_nothing_paid_out_is_not_sent(self):
    with mock.patch("it01.labels.ask") as said: self.assertEqual(spending(PAID_IN), ())
    said.assert_not_called()

  @unittest.skipIf(any(importlib.util.find_spec(m) is None for m in ("numpy", "onnxruntime", "tokenizers")), "the local extra is not installed")
  def test_a_model_file_labels_the_debits_when_one_is_named(self):
    with mock.patch("it01.labels.IT01_LABELLER", "labeller.onnx"):
      with mock.patch("it01.local.classified", return_value=("pension", "no_claim", "no_claim")) as sorted_by: found = spending(STATEMENT)
    self.assertEqual((len(found), sorted_by.call_args.args[1]), (3, PROMPT))

  def test_the_shipped_table_says_how_every_kind_counts(self):
    table = paying()
    self.assertEqual(sorted({*table.claims, *table.certificates, *table.business, *table.picks, *table.aside}), sorted(PROMPT.kinds))

  def test_a_table_that_leaves_a_kind_out_or_uses_one_twice_is_refused(self):
    held = data("paying")
    for change, says in (({"aside": ["unclear"]}, r"nothing of how \['no_claim'\]"),
                         ({"aside": ["unclear", "no_claim", "pension"]}, r"\['pension'\] more than one use"),
                         ({"claims": {"pension": {"fact": "windfall", "asking": "yes"}}}, r"unknown facts \['windfall'\]"),
                         ({"headlines": {"gift": "was this a gift?"}}, r"headlines for unknown kinds \['gift'\]")):
      with self.subTest(says), mock.patch("it01.kinds.data", return_value=held | change):
        with self.assertRaisesRegex(ValueError, says): paying()

if __name__ == "__main__": unittest.main()
