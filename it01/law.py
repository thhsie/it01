from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, auto

DOCS = {"ita": "https://www.mra.mu/download/ITAConsolidated.pdf", "regs": "https://www.mra.mu/download/ITaxRegulationsGN78of1996.pdf"}

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

class Basis(Enum):
  COST = auto()
  BASE_VALUE = auto()

class AssetKind(Enum):
  INDUSTRIAL_PREMISES = auto()
  COMMERCIAL_PREMISES = auto()
  HOTEL = auto()
  SHIP_OR_AIRCRAFT = auto()
  MOTOR_VEHICLE = auto()
  COMPUTER = auto()
  ELECTRONIC_EQUIPMENT = auto()
  FURNITURE = auto()
  OTHER_PLANT = auto()
  AGRICULTURAL_IMPROVEMENT = auto()
  RESEARCH_AND_DEVELOPMENT = auto()
  GOLF_COURSE = auto()
  PATENT = auto()
  GREEN_TECHNOLOGY = auto()
  LANDSCAPING = auto()
  SOLAR_ENERGY_UNIT = auto()
  OTHER_CAPITAL_ITEM = auto()

ALLOWANCES = {
  AssetKind.INDUSTRIAL_PREMISES: (Decimal("0.05"), Basis.COST, False),
  AssetKind.COMMERCIAL_PREMISES: (Decimal("0.05"), Basis.COST, False),
  AssetKind.HOTEL: (Decimal("0.30"), Basis.BASE_VALUE, False),
  AssetKind.SHIP_OR_AIRCRAFT: (Decimal("0.20"), Basis.BASE_VALUE, True),
  AssetKind.MOTOR_VEHICLE: (Decimal("0.25"), Basis.BASE_VALUE, True),
  AssetKind.COMPUTER: (Decimal("0.50"), Basis.BASE_VALUE, True),
  AssetKind.ELECTRONIC_EQUIPMENT: (Decimal("1"), Basis.COST, True),
  AssetKind.FURNITURE: (Decimal("0.20"), Basis.BASE_VALUE, True),
  AssetKind.OTHER_PLANT: (Decimal("0.35"), Basis.BASE_VALUE, True),
  AssetKind.AGRICULTURAL_IMPROVEMENT: (Decimal("0.25"), Basis.BASE_VALUE, False),
  AssetKind.RESEARCH_AND_DEVELOPMENT: (Decimal("0.50"), Basis.COST, False),
  AssetKind.GOLF_COURSE: (Decimal("0.15"), Basis.BASE_VALUE, False),
  AssetKind.PATENT: (Decimal("0.25"), Basis.BASE_VALUE, False),
  AssetKind.GREEN_TECHNOLOGY: (Decimal("0.50"), Basis.COST, True),
  AssetKind.LANDSCAPING: (Decimal("0.50"), Basis.COST, False),
  AssetKind.SOLAR_ENERGY_UNIT: (Decimal("1"), Basis.COST, False),
  AssetKind.OTHER_CAPITAL_ITEM: (Decimal("0.05"), Basis.COST, False),
}
SMALL_PLANT = Decimal(60000)
MOTOR_VEHICLE_CAP = Decimal(3000000)
ALLOWANCE_SRC = (Source("ita", "s.2 base value", 13), Source("ita", "s.24", 43), Source("regs", "regulation 7", 8),
                 Source("regs", "Fourth Schedule", 46))
BUSINESS_SRC = (Source("ita", "s.10(1)(b)", 31), Source("ita", "s.18(1)", 38))
DISALLOWED = ("depreciation", "entertainment_gifts_and_donations")
DISALLOWED_SRC = (Source("ita", "s.26(1)", 46),)
