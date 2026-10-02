import random, unittest
from dataclasses import replace
from decimal import Decimal
from typing import Any
from it01.asks import Asked, balance, based, derived, from_answers, priced, projected, proposals, questions, subject_of, tables, worded
from it01.held import Case, Document, Line, Payment, Reading, loaded, opened, written
from it01.keep import ENTERED, answered, case, confirm, forgot, keep, noted, removed, said_to, set_fact, unconfirmed, with_year

T = tables()
WORDS = ("CLIENT A", "CLIENT B", "TENANT", "DIVIDEND", "CASH DEPOSIT", "TRANSFER", "INSURER", "PENSION PLAN", "SCHOOL", "SHOP", "ELECTRICITY BILL")
MONTHS = ("2025-06", "2025-07", "2025-09", "2025-12", "2026-03", "2026-06", "2026-07", None)
AMOUNTS = ("100.00", "2500.00", "15000.00", "75000.00", "1234.56", "300000.00")
UNDATED = "15/13/2025"
SETS = (("dependants", "2"), ("salary", "500000"), ("salary", ""), ("housing_loan_interest", "40000"), ("business.gross_income", "200000"),
        ("tax_deducted_at_source", "3000"), ("medical_insurance", "10000"))

def statement(r:random.Random, held:Case, name:str) -> Case:
  paid = []
  for _ in range(r.randint(0, 8)):
    way, month = r.choice(("in", "out")), r.choice(MONTHS)
    label = r.choice(list((T.into if way == "in" else T.out).prompt.kinds))
    date = f"15/{month[5:]}/{month[:4]}" if month else UNDATED
    check = r.choice(("ok", "ok", "does not agree", "not checked"))
    paid.append(Payment(name, way, Decimal(r.choice(AMOUNTS)), date, r.choice(WORDS), label, check, month))
  if paid and held.payments and r.random() < 0.4: paid.append(replace(r.choice(list(held.payments.values())), document=name))
  return noted(held, name, Document(T.into.prompt.name, name, name), [(worded(p), p) for p in paid], [], [])

def form(r:random.Random, held:Case, name:str) -> Case:
  read = [Reading(name, "salary", Decimal(r.choice(("600000.00", "1107000.00"))), "Net emoluments"),
          Reading(name, "paye_withheld", Decimal(r.choice(("20000.00", "71401.00"))), "Tax withheld")]
  bonus = Line(name, Decimal("5000.00"), "Bonus", "which line is this", (("net_emoluments", "net pay"), ("none", "neither")))
  lines = [("5,000.00 on the line Bonus", bonus)] if r.random() < 0.5 else []
  return noted(held, name, Document("statement of emoluments", name, name, ends=held.year.get("to") or "2026-06"), [], read, lines)

def waiting(held:Case) -> list[Asked]: return [q for q in questions(held, T, proposals(held, T)[0]) if said_to(held, q) is None]

def moved(r:random.Random, held:Case, n:int) -> Case:
  match r.choice(("add", "add", "answer", "answer", "answer", "forget", "confirm", "unconfirm", "set", "remove", "year")):
    case "add": return (statement if r.random() < 0.75 else form)(r, held, f"doc{n}.txt")
    case "answer" if subjects := [q.subject for q in waiting(held)] + [*held.payments, *held.readings]:
      q = subject_of(held, T, subject := r.choice(subjects))
      return answered(held, T, subject, r.choice([c for c, _ in q.choices]))
    case "forget" if held.decisions: return forgot(held, T, r.choice(list(held.decisions)))
    case "confirm" if proposed := proposals(held, T)[0]: return confirm(held, T, r.choice(list(proposed)))
    case "unconfirm" if names := [name for name in held.confirmed if held.sources[name] != ENTERED]: return unconfirmed(held, r.choice(names))
    case "set": return set_fact(held, T, *r.choice(SETS))
    case "remove" if held.documents: return removed(held, T, r.choice(list(held.documents)))
    case "year" if not any(d.ends for d in held.documents.values()): return with_year(held, r.choice(("2025-07", "2024-07")))
  return held

CASES:list[tuple[str, Case]] = []
for seed in range(30):
  r, held = random.Random(seed), opened({"resident": True})
  for n in range(20):
    held = moved(r, held, n)
    CASES.append((f"seed {seed} step {n}", held))

def flat(given:dict[str, Any]) -> dict[str, Any]:
  ret = {}
  for k, v in given.items(): ret |= {f"{k}.{f}": one for f, one in v.items()} if isinstance(v, dict) else {k: v}
  return ret

class TestMoves(unittest.TestCase):
  def test_every_case_reads_back_and_shows(self):
    for at, held in CASES:
      with self.subTest(at):
        self.assertEqual(opened(loaded(written(held))), held)
        self.assertTrue(case(held, T))
        self.assertTrue(keep(held, T))

  def test_every_answer_offered_is_taken_and_sticks(self):
    for at, held in CASES:
      for q in waiting(held):
        for choice in [c for c, _ in q.choices] + (["payments 1", str((q.amount / 2).quantize(Decimal("0.01")))] if q.share else []):
          with self.subTest(at, subject=q.subject, choice=choice):
            after = answered(held, T, q.subject, choice)
            asked = [x for x in questions(after, T, proposals(after, T)[0]) if x.subject == q.subject]
            stored = choice
            self.assertTrue(all(said_to(after, x) == stored for x in asked))
            moved = {f for f in after.confirmed.keys() | held.confirmed.keys() if after.confirmed.get(f) != held.confirmed.get(f)}
            self.assertLessEqual(moved, from_answers(after, T) | from_answers(held, T))
            now, was = flat(after.given), flat(held.given)
            self.assertLessEqual({f for f in now.keys() | was.keys() if now.get(f) != was.get(f)}, moved)
            self.assertLessEqual({f for f in after.sources.keys() | held.sources.keys() if after.sources.get(f) != held.sources.get(f)}, moved)
            kept = replace(after, decisions=held.decisions, given=held.given, confirmed=held.confirmed, sources=held.sources)
            self.assertEqual(kept, held)

  def test_a_price_is_what_the_answer_changes(self):
    for at, held in CASES:
      base = based(held, T)
      assert base.before is not None
      for q in waiting(held):
        for choice, fig in priced(held, T, q, base).items():
          after = answered(held, T, q.subject, choice)
          with self.subTest(at, subject=q.subject, choice=choice):
            self.assertEqual(balance(projected(after, derived(after, T))).amt - base.before.amt, fig.amt)

  def test_confirming_every_figure_leaves_nothing_proposed(self):
    for at, held in CASES:
      for name in proposals(held, T)[0]: held = confirm(held, T, name)
      with self.subTest(at): self.assertEqual(proposals(held, T)[0], {})

if __name__ == "__main__": unittest.main()
