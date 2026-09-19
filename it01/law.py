from dataclasses import dataclass
from decimal import Decimal

DOCS = {"ita": "https://www.mra.mu/download/ITAConsolidated.pdf"}

@dataclass(frozen=True)
class Source:
  doc: str
  section: str
  page: int

  @property
  def url(self) -> str: return f"{DOCS[self.doc]}#page={self.page}"

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
FAIR_SHARE_THRESHOLD = Decimal(12000000)
FAIR_SHARE_RATE = Decimal("0.15")
FAIR_SHARE_SRC = (Source("ita", "s.16B", 35), Source("ita", "s.16C", 37))
CREDITS_SRC = (Source("ita", "s.93(1)", 115), Source("ita", "s.103", 121), Source("ita", "s.111(2)", 123), Source("ita", "s.111G", 129),
               Source("ita", "s.152(1)", 222))
LOSSES_SRC = (Source("ita", "s.20", 40),)
