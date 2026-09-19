from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class Source:
  doc: str
  section: str
  page: int

BANDS = ((Decimal(500000), Decimal(0)), (Decimal(500000), Decimal("0.10")), (Decimal("Infinity"), Decimal("0.20")))
BANDS_SRC = (Source("ita", "s.4", 26), Source("ita", "First Schedule Part I", 262))
