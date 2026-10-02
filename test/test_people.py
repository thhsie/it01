import random, unittest
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from it01.asks import EACH, OUT, SAME, Asked, proposals, questions, tables, worded, year_of
from it01.held import Case, Document, Payment, Reading, opened
from it01.keep import answered, confirm, noted, said_to, set_fact, with_year
from it01.tax import Facts, from_json

T = tables()
YEAR = year_of("2025-07")
ZERO = Decimal("0.00")

@dataclass(frozen=True)
class Row:
  way: str
  amount: Decimal
  month: str
  description: str
  label: str
  truth: str

@dataclass
class PersonCtx:
  r: random.Random
  rows: list[Row] = field(default_factory=list)
  facts: dict[str, Any] = field(default_factory=lambda: {"resident": True})
  form: tuple[Decimal, Decimal]|None = None
  approved: bool = True
  share: Decimal = Decimal(1)
  certificates: dict[str, str] = field(default_factory=dict)
  kept: dict[str, list[Row]] = field(default_factory=dict)

  def amt(self, lo:int, hi:int) -> Decimal: return Decimal(self.r.randint(lo, hi)) + Decimal(self.r.choice(("0.00", "0.50", "0.25")))

  def row(self, way:str, amt:Decimal, description:str, label:str, truth:str|None=None, month:str|None=None, fact:str|None=None) -> None:
    self.rows.append(Row(way, amt, month or self.r.choice(YEAR), description, label, truth or label))
    if fact: self.add(fact, amt)

  def add(self, fact:str, amt:Decimal) -> None:
    part, _, rest = fact.partition(".")
    if not rest: self.facts[part] = self.facts.get(part, ZERO) + amt
    else: self.facts[part] = (block := self.facts.get(part, {})) | {rest: block.get(rest, ZERO) + amt}

  def chance(self, odds:float) -> bool: return self.r.random() < odds

def person(r:random.Random) -> PersonCtx:
  p = PersonCtx(r)
  if p.chance(0.6):
    salary, withheld = Decimal(r.randint(40, 120) * 10000), Decimal(r.randint(0, 9) * 1000)
    p.form, p.facts["salary"], p.facts["paye_withheld"] = (salary, withheld), salary, withheld
    for m in YEAR: p.row("in", ((salary - withheld) / 12).quantize(Decimal("0.01")), "SALARY FROM EMPLOYER", "pay", month=m)
  if trading := p.chance(0.7):
    starting = p.chance(0.15)
    for m in r.sample(YEAR, 0 if starting else r.randint(1, 12)):
      p.row("in", p.amt(2000, 90000), f"CLIENT {r.randint(1, 4)}", "business", month=m, fact="business.gross_income")
    for _ in range(0 if starting else r.randint(0, 3)):
      if p.chance(0.3): p.row("in", p.amt(500, 20000), "CASH DEPOSIT", "cash", "other")
      else: p.row("in", p.amt(500, 20000), "CASH DEPOSIT", "cash", "business", fact="business.gross_income")
    for _ in range(r.randint(1 if starting else 0, 6)):
      p.row("out", p.amt(300, 15000), "SUPPLIER", "business_expense", fact="business.other_expenses")
  for _ in range(r.randint(0, 2)): p.row("in", p.amt(500, 5000), "OWN TRANSFER", "other")
  for _ in range(r.randint(0, 2)): p.row("in", p.amt(500, 5000), "GIFT FROM FAMILY", "unclear", "other")
  if p.chance(0.3):
    for m in r.sample(YEAR, 3): p.row("in", p.amt(5000, 15000), "TENANT", "rent", month=m, fact="rent")
  if p.chance(0.3): p.row("in", p.amt(1000, 30000), "DIVIDEND FROM A COMPANY", "dividend", fact="resident_dividends")
  if p.chance(0.3): p.row("in", p.amt(10, 2000), "INTEREST PAID", "interest", fact="exempt_interest")
  if p.chance(0.4):
    p.approved = p.chance(0.8)
    for m in r.sample(YEAR, 4):
      p.row("out", p.amt(1000, 5000), "PENSION PLAN", "pension", month=m, fact="pension_contributions" if p.approved else None)
  if p.chance(0.3): p.row("out", p.amt(1000, 10000), "CHARITY", "donation", fact="electronic_donations")
  if p.chance(0.3):
    for m in r.sample(YEAR, 2): p.row("out", p.amt(2000, 6000), "HEALTH INSURER", "medical_insurance", month=m)
    figure = p.amt(5000, 20000)
    p.facts["medical_insurance"], p.certificates["medical_insurance"] = [figure], str(figure)
  if p.chance(0.3):
    for m in r.sample(YEAR, 3): p.row("out", p.amt(10000, 20000), "HOME LOAN", "housing_loan", month=m)
    figure = p.amt(20000, 90000)
    p.facts["housing_loan_interest"], p.certificates["housing_loan_interest"] = figure, str(figure)
  for _ in range(r.randint(0, 5)): p.row("out", p.amt(50, 3000), "SHOP", "no_claim")
  if trading and p.chance(0.5):
    p.share = Decimal("0.5")
    for m in r.sample(YEAR, 3): p.row("out", Decimal(r.randint(500, 2000) * 2), "ELECTRICITY BILL", "bills", month=m)
    p.add("business.utilities", sum((one.amount for one in p.rows if one.label == "bills"), ZERO) * p.share)
  for _ in range(r.randint(0, 3)):
    if trading and p.chance(0.5): p.row("in", p.amt(100, 2000), "REFUND FROM SUPPLIER", "refund", "business_refund", fact="business.other_income")
    else: p.row("in", p.amt(100, 2000), "REFUND FROM SHOP", "refund")
  if trading and p.chance(0.5):
    for m in r.sample(YEAR, 4): p.row("out", p.amt(50, 300), "ACCOUNT FEE", "bank_charges", month=m, fact="business.bank_charges")
  if trading and p.chance(0.5):
    for m in r.sample(YEAR[4:], r.randint(1, 3)):
      p.row("out", p.amt(5000, 40000), "INCOME TAX QUARTERLY", "tax_paid", month=m, fact="quarterly_tax_paid")
    if p.chance(0.5): p.row("out", p.amt(5000, 40000), "INCOME TAX BALANCE", "tax_paid", "earlier_tax", YEAR[2])
  for _ in range(r.randint(0, 2)): p.row("in", p.amt(2000, 50000), "CLIENT 9", "business", month=r.choice(("2025-05", "2026-08")))
  return p

def statement(held:Case, name:str, rows:list[Row]) -> Case:
  paid = [Payment(name, one.way, one.amount, f"15/{one.month[5:]}/{one.month[:4]}", one.description, one.label, "ok", one.month) for one in rows]
  return noted(held, name, Document(T.into.prompt.name, name, name), [(worded(x), x) for x in paid], [], [])

def quarter(month:str) -> int: return YEAR.index(month) // 3 if month in YEAR else 0 if month < YEAR[0] else 3

def case_of(p:PersonCtx) -> Case:
  held = with_year(opened({"resident": True}), YEAR[0])
  rows = p.rows[:]
  p.r.shuffle(rows)
  layout = p.r.choice(("one", "halves", "quarters"))
  if layout == "quarters":
    parts = [[one for one in rows if quarter(one.month) == n] for n in range(4)]
    if p.chance(0.4):
      lost = p.r.randrange(4)
      p.kept[f"bank{lost}.txt"] = parts[lost]
  else: parts = [rows[:(half := len(rows) // 2)], rows[max(0, half - 3):]] if layout == "halves" and len(rows) > 6 else [rows]
  for n, part in enumerate(parts):
    if f"bank{n}.txt" not in p.kept: held = statement(held, f"bank{n}.txt", part)
  return held

def truth_of(p:PersonCtx, held:Case, key:str) -> str:
  pay = held.payments[key]
  return next(one.truth for one in p.rows if (one.way, one.amount, one.description, one.month) == (pay.way, pay.amount, pay.description, pay.month))

def replied(p:PersonCtx, held:Case, q:Asked) -> Case:
  choices = dict(q.choices)
  if q.subject in held.payments:
    truth = truth_of(p, held, q.subject)
    return answered(held, T, q.subject, SAME if SAME in choices else truth if truth in choices else OUT)
  if EACH in choices:
    truths = {truth_of(p, held, key) for key in q.paid}
    if len(truths) > 1: return answered(held, T, q.subject, EACH)
    return answered(held, T, q.subject, one if (one := truths.pop()) in choices else OUT)
  if q.closes == "salary" and p.form:
    salary, withheld = p.form
    read = [Reading("form.txt", "salary", salary, "Net emoluments"), Reading("form.txt", "paye_withheld", withheld, "Tax withheld")]
    return noted(held, "form.txt", Document("statement of emoluments", "form.txt", "form.txt", ends=YEAR[-1]), [], read, [])
  if q.closes: return set_fact(held, T, q.closes, p.certificates[q.closes])
  if "none" in choices:
    missing = q.about.removeprefix("no statement covers ").split(", ")
    if found := next((name for name, rows in p.kept.items() if any(one.month in missing for one in rows)), None):
      return statement(held, found, p.kept.pop(found))
    return answered(held, T, q.subject, "none")
  if "business" in choices: return answered(held, T, q.subject, "business" if "business" in p.facts else "not")
  kind = held.payments[q.paid[0]].label
  def picked(truth:str) -> str:
    ours = [str(n) for n, key in enumerate(q.paid, 1) if truth_of(p, held, key) == truth]
    return f"payments {', '.join(ours)}" if ours else "no"
  said = {"bills": str(q.amount * p.share), "business_expense": "yes", "bank_charges": "yes", "donation": "yes",
          "pension": "yes" if p.approved else "no", "tax_paid": picked("tax_paid"), "refund": picked("business_refund")}
  if kind not in said: raise AssertionError(f"the person has no answer for {kind}")
  return answered(held, T, q.subject, said[kind])

def settled(p:PersonCtx) -> Case:
  held = case_of(p)
  for _ in range(60):
    if not (waiting := [q for q in questions(held, T, proposals(held, T)[0]) if said_to(held, q) is None]): break
    held = replied(p, held, waiting[0])
  else: raise AssertionError("questions still open after 60 answers")
  while proposed := proposals(held, T)[0]:
    for name in proposed: held = confirm(held, T, name)
  return held

class TestPeople(unittest.TestCase):
  def test_a_truthful_person_ends_with_their_true_tax(self):
    for seed in range(200):
      with self.subTest(seed=seed):
        p = person(random.Random(seed))
        self.assertEqual(from_json(Facts, settled(p).given), from_json(Facts, p.facts))

if __name__ == "__main__": unittest.main()
