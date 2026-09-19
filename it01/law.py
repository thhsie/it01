from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class Source:
  doc: str
  section: str
  page: int

BANDS = ((Decimal(500000), Decimal(0)), (Decimal(500000), Decimal("0.10")), (Decimal("Infinity"), Decimal("0.20")))
BANDS_SRC = (Source("ita", "s.4", 26), Source("ita", "First Schedule Part I", 262))
CHARGEABLE_SRC = (Source("ita", "s.2", 13), Source("ita", "s.10", 30), Source("ita", "Second Schedule Part II Sub-Part B item 1", 267))
RESIDENT_SRC = (Source("ita", "s.27(1)", 47),)
DEPENDANTS = (Decimal(0), Decimal(110000), Decimal(190000), Decimal(275000), Decimal(355000))
DEPENDANTS_SRC = (Source("ita", "s.27(2)", 47), Source("ita", "Third Schedule Part I", 280))
MEDICAL = (Decimal(25000), Decimal(50000), Decimal(70000), Decimal(90000), Decimal(110000))
MEDICAL_SRC = (Source("ita", "s.27B", 51), Source("ita", "Third Schedule Part II", 281))
INTEREST_BAR = Decimal(4000000)
INTEREST_SRC = (Source("ita", "s.27A", 50), Source("ita", "s.27A(4)(c)", 51), Source("ita", "s.27A(5)", 51))
