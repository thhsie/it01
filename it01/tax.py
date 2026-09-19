from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from it01.law import BANDS, BANDS_SRC, Source

ZERO = Decimal(0)

@dataclass(frozen=True)
class Figure:
  rule: str
  amt: Decimal
  src: tuple[Source, ...]

def income_tax(chargeable:Decimal) -> Figure:
  whole = chargeable.is_finite() and chargeable >= 0 and chargeable == chargeable.to_integral_value()
  if not whole: raise ValueError(f"invalid chargeable income {chargeable}")
  ret, lo = ZERO, ZERO
  for width, rate in BANDS: ret, lo = ret + (max(ZERO, min(chargeable - lo, width)) * rate).quantize(Decimal(1), ROUND_HALF_UP), lo + width
  return Figure("income tax", ret, BANDS_SRC)
