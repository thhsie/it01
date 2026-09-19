from dataclasses import dataclass, fields
from decimal import ROUND_HALF_UP, Decimal
from it01.law import (BANDS, BANDS_SRC, CHARGEABLE_SRC, DEPENDANTS, DEPENDANTS_SRC, INTEREST_BAR, INTEREST_SRC, MEDICAL, MEDICAL_SRC, RESIDENT_SRC,
                      Source, FAIR_SHARE_RATE, FAIR_SHARE_SRC, FAIR_SHARE_THRESHOLD)

ZERO = Decimal(0)

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
  resident_dividends: Decimal = ZERO
  housing_loan_interest: Decimal = ZERO
  medical_insurance: Decimal = ZERO
  other_reliefs: Decimal = ZERO

  def __post_init__(self) -> None:
    if self.dependants < 0: raise ValueError(f"invalid dependants {self.dependants}")
    for f in (f for f in fields(self) if f.type is Decimal):
      if not (isinstance(v := getattr(self, f.name), Decimal) and v.is_finite() and v >= 0): raise ValueError(f"invalid {f.name} {v}")

  @property
  def gross(self) -> Decimal:
    return self.salary + self.taxable_transport_allowance + self.performance_bonus + self.statutory_bonus + self.other_income

def rupees(x:Decimal) -> Decimal: return x.quantize(Decimal(1), ROUND_HALF_UP)

def chargeable_income(f:Facts) -> Figure:
  amt, src = f.gross, list(CHARGEABLE_SRC + RESIDENT_SRC)
  if f.resident:
    cnt = min(f.dependants, len(DEPENDANTS) - 1)
    interest = f.housing_loan_interest if f.gross + f.resident_dividends <= INTEREST_BAR else ZERO
    amt -= DEPENDANTS[cnt] + min(f.medical_insurance, MEDICAL[cnt]) + interest + f.other_reliefs
    src += DEPENDANTS_SRC + MEDICAL_SRC + INTEREST_SRC
  return Figure("chargeable income", rupees(max(ZERO, amt)), tuple(src))

def income_tax(chargeable:Decimal) -> Figure:
  whole = chargeable.is_finite() and chargeable >= 0 and chargeable == chargeable.to_integral_value()
  if not whole: raise ValueError(f"invalid chargeable income {chargeable}")
  ret, lo = ZERO, ZERO
  for width, rate in BANDS: ret, lo = ret + rupees(max(ZERO, min(chargeable - lo, width)) * rate), lo + width
  return Figure("income tax", ret, BANDS_SRC)

def assess(f:Facts) -> tuple[Figure, ...]:
  ci = chargeable_income(f)
  tax = income_tax(ci.amt)
  share = Figure("fair share contribution", rupees(max(ZERO, ci.amt + f.resident_dividends - FAIR_SHARE_THRESHOLD) * FAIR_SHARE_RATE), FAIR_SHARE_SRC)
  return ci, tax, share, Figure("total tax", tax.amt + share.amt, tax.src + share.src)
