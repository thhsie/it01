from dataclasses import MISSING, dataclass, fields
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Any
from it01.law import (BANDS, BANDS_SRC, CHARGEABLE_SRC, DEPENDANTS, DEPENDANTS_SRC, INTEREST_BAR, INTEREST_SRC, MEDICAL, MEDICAL_SRC, RESIDENT_SRC,
                      Source, CREDITS_SRC, FAIR_SHARE_RATE, FAIR_SHARE_SRC, FAIR_SHARE_THRESHOLD, LOSSES_SRC)

ZERO = Decimal(0)
AMOUNT_LIMIT = Decimal(10) ** 15
JSON_TYPES: dict[Any, tuple[type, ...]] = {bool: (bool,), int: (int,), Decimal: (int, Decimal)}

@dataclass(frozen=True)
class Figure:
  rule: str
  amt: Decimal
  src: tuple[Source, ...]

@dataclass(frozen=True)
class Facts:
  resident: bool
  dependants: int = 0
  salary: Decimal = ZERO
  taxable_transport_allowance: Decimal = ZERO
  performance_bonus: Decimal = ZERO
  statutory_bonus: Decimal = ZERO
  other_income: Decimal = ZERO
  business_gross_income: Decimal = ZERO
  business_deductions: Decimal = ZERO
  losses_brought_forward: Decimal = ZERO
  resident_dividends: Decimal = ZERO
  housing_loan_interest: Decimal = ZERO
  medical_insurance: Decimal = ZERO
  other_reliefs: Decimal = ZERO
  paye_withheld: Decimal = ZERO
  tax_deducted_at_source: Decimal = ZERO
  quarterly_tax_paid: Decimal = ZERO

  def __post_init__(self) -> None:
    if self.dependants < 0: raise ValueError(f"invalid dependants {self.dependants}")
    for f in (f for f in fields(self) if f.type is Decimal):
      if not (isinstance(v := getattr(self, f.name), Decimal) and v.is_finite() and 0 <= v < AMOUNT_LIMIT and v == v.quantize(Decimal("0.01"))):
        raise ValueError(f"invalid {f.name} {v}")

  @property
  def emoluments(self) -> Decimal: return self.salary + self.taxable_transport_allowance + self.performance_bonus + self.statutory_bonus

def to_facts(raw:Any) -> Facts:
  if not isinstance(raw, dict): raise ValueError("facts must be a JSON object")
  types = {f.name: f.type for f in fields(Facts)}
  if unknown := sorted(set(raw) - set(types)): raise ValueError(f"unknown facts {unknown}")
  if missing := sorted(f.name for f in fields(Facts) if f.default is MISSING and f.name not in raw): raise ValueError(f"missing facts {missing}")
  for k, v in raw.items():
    if type(v) not in JSON_TYPES[types[k]]: raise ValueError(f"invalid {k} {v} of type {type(v).__name__}")
  vals: dict[str, Any] = {k: Decimal(v) if types[k] is Decimal else v for k, v in raw.items()}
  return Facts(**vals)

def rupees(x:Decimal) -> Decimal: return x.quantize(Decimal(1), ROUND_HALF_UP)

def net_income_and_losses(f:Facts) -> tuple[Decimal, Decimal]:
  business = f.business_gross_income - f.business_deductions
  other = f.other_income + max(ZERO, business)
  used = min(other, losses := f.losses_brought_forward + max(ZERO, -business))
  return f.emoluments + other - used, losses - used

def chargeable_income(f:Facts) -> Figure:
  amt, src = net_income_and_losses(f)[0], list(CHARGEABLE_SRC + RESIDENT_SRC + LOSSES_SRC)
  if f.resident:
    cnt = min(f.dependants, len(DEPENDANTS) - 1)
    interest = f.housing_loan_interest if amt + f.resident_dividends <= INTEREST_BAR else ZERO
    amt -= DEPENDANTS[cnt] + min(f.medical_insurance, MEDICAL[cnt]) + interest + f.other_reliefs
    src += DEPENDANTS_SRC + MEDICAL_SRC + INTEREST_SRC
  return Figure("chargeable income", rupees(max(ZERO, amt)), tuple(src))

def income_tax(chargeable:Decimal) -> Figure:
  whole = chargeable.is_finite() and chargeable >= 0 and chargeable == chargeable.to_integral_value()
  if not whole: raise ValueError(f"invalid chargeable income {chargeable}")
  ret, lo = ZERO, ZERO
  for width, rate in BANDS: ret, lo = ret + (max(ZERO, min(chargeable - lo, width)) * rate).quantize(Decimal(1), ROUND_DOWN), lo + width
  return Figure("income tax", ret, BANDS_SRC)

def assess(f:Facts) -> tuple[Figure, ...]:
  ci = chargeable_income(f)
  tax = income_tax(ci.amt)
  share = Figure("fair share contribution", rupees(max(ZERO, ci.amt + f.resident_dividends - FAIR_SHARE_THRESHOLD) * FAIR_SHARE_RATE), FAIR_SHARE_SRC)
  total = Figure("total tax", tax.amt + share.amt, tax.src + share.src)
  paid = f.paye_withheld + f.tax_deducted_at_source + f.quarterly_tax_paid
  balance = Figure("balance of tax", total.amt - paid, total.src + CREDITS_SRC)
  return ci, tax, share, total, balance, Figure("losses carried forward", net_income_and_losses(f)[1], LOSSES_SRC)
