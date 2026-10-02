from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, auto

DOCS = {"ita": "https://www.mra.mu/download/ITAConsolidated.pdf", "regs": "https://www.mra.mu/download/ITaxRegulationsGN78of1996.pdf",
        "cps": "https://www.mra.mu/download/GuidelinesCPS.pdf"}

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
INVESTMENTS = {"solar_energy": (Source("ita", "s.27C", 52),), "rainwater_harvesting": (Source("ita", "s.27E", 53),),
               "fast_charger": (Source("ita", "s.27F", 53),)}
DUTY_SRC = (Source("ita", "s.17(1)", 37), Source("ita", "s.17(2)", 37))
DEPENDANTS = (Decimal(0), Decimal(110000), Decimal(190000), Decimal(275000), Decimal(355000))
DEPENDANTS_SRC = (Source("ita", "s.27(2)", 47), Source("ita", "Third Schedule Part I", 280))
DEPENDANT_LIMITS = (Decimal(110000), Decimal(80000), Decimal(85000), Decimal(80000))
DEPENDANT_INCOME_SRC = (Source("ita", "s.27(5)", 48), Source("ita", "s.27(6)", 48))
MEDICAL = (Decimal(25000), Decimal(25000), Decimal(20000), Decimal(20000), Decimal(20000))
MEDICAL_SRC = (Source("ita", "s.27B", 51), Source("ita", "Third Schedule Part II", 281))
HEADS: dict[str, tuple[Source, ...]] = {
  "basic_retirement_pension": (Source("ita", "s.10(1)(e)", 31),),
  "state_pension": (Source("ita", "s.10(1)(d)", 31),),
  "social_retirement_benefit": (Source("ita", "s.10(1)(d)", 31),),
  "taxable_interest": (Source("ita", "s.10(1)(d)", 31),),
  "royalty": (Source("ita", "s.10(1)(c)", 31),),
  "premium": (Source("ita", "s.10(1)(c)", 31),),
  "annuity": (Source("ita", "s.10(1)(d)", 31),),
  "charges": (Source("ita", "s.10(1)(d)", 31),),
  "other_source": (Source("ita", "s.10(1)(g)", 31),),
  "foreign_dividend": (Source("ita", "s.5(1)", 27), Source("ita", "s.5(3)", 28)),
  "foreign_rent": (Source("ita", "s.5(1)", 27), Source("ita", "s.5(3)", 28)),
  "foreign_interest": (Source("ita", "s.5(1)", 27), Source("ita", "s.5(3)", 28)),
  "foreign_other": (Source("ita", "s.5(1)", 27), Source("ita", "s.5(3)", 28)),
}
ABROAD = ("foreign_dividend", "foreign_rent", "foreign_interest", "foreign_other")

class Addition(Enum):
  NONE = auto()
  RETIRED = auto()
  DISABLED = auto()

ADDITION = Decimal(50000)
RETIRED_EMOLUMENTS = Decimal(50000)
ADDITION_SRC = (Source("ita", "s.27(2A)", 47), Source("ita", "s.27(7)", 49))
TERTIARY = Decimal(500000)
TERTIARY_TUITION = Decimal(34800)
TERTIARY_YEARS = 6
TERTIARY_CHILDREN = 4
TERTIARY_SRC = (Source("ita", "s.27(6A)", 48), Source("ita", "Third Schedule Part I item 2", 280), Source("ita", "Third Schedule Part I item 3", 280))
CAPPED: dict[str, tuple[Decimal, tuple[Source, ...]]] = {
  "school_fees": (Decimal(60000), (Source("ita", "Third Schedule Part I item 4", 280),)),
  "electronic_donations": (Decimal(100000), (Source("ita", "s.27DA", 52),)),
  "pension_contributions": (Decimal(50000), (Source("ita", "s.27DB", 52),)),
  "carer_wages": (Decimal(30000), (Source("ita", "s.27DC", 52),)),
}
INTEREST_BAR = Decimal(4000000)
INTEREST_SRC = (Source("ita", "s.27A", 50), Source("ita", "s.27A(4)(c)", 51), Source("ita", "s.27A(5)", 51))
FAIR_SHARE_THRESHOLD = Decimal(12000000)
FAIR_SHARE_RATE = Decimal("0.15")
FAIR_SHARE_SRC = (Source("ita", "s.16B", 35), Source("ita", "s.16C", 37))
CREDITS_SRC = (Source("ita", "s.93(1)", 115), Source("ita", "s.103", 121), Source("ita", "s.111(2)", 123), Source("ita", "s.111G", 129),
               Source("ita", "s.152(1)", 222))
LOSSES_SRC = (Source("ita", "s.20", 40),)
YEAR_STARTS = 7
YEAR_SRC = (Source("ita", "s.2", 19), Source("ita", "s.2", 26))
EARLIER_MONTHS = 4
EARLIER_SRC = (Source("cps", "4. Due Dates", 3), Source("cps", "12. Annual Return", 9))
QUARTER_BANDS = ((Decimal(125000), Decimal(0)), (Decimal(125000), Decimal("0.10")), (Decimal("Infinity"), Decimal("0.20")))
QUARTER_BANDS_SRC = (Source("ita", "s.108", 123), Source("cps", "9. Calculation of Tax", 8))
QUARTER_INCOME_SRC = (Source("ita", "s.105", 121), Source("ita", "s.107(2)", 122))
QUARTER_CREDIT_SRC = (Source("ita", "s.111G", 129), Source("cps", "10. Tax Deducted at Source", 9))
QUARTER_RELIEF = Decimal("0.25")

class Period(Enum):
  YEAR = auto()
  QUARTER = auto()

RATES = {Period.YEAR: (BANDS, BANDS_SRC), Period.QUARTER: (QUARTER_BANDS, QUARTER_BANDS_SRC)}

@dataclass(frozen=True)
class AllowanceRule:
  wording: str
  part: Decimal
  src: tuple[Source, ...]

ALLOWANCE_RULES = {Period.YEAR: AllowanceRule("annual allowance on", Decimal(1), ()),
                   Period.QUARTER: AllowanceRule("a quarter of the annual allowance on", Decimal("0.25"),
                                             (Source("cps", "7. Annual allowance", 5),))}

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
LENDING_EXEMPT = Decimal("0.8")
BAD_DEBT_SRC = (Source("ita", "s.21(2A)", 41),)
LENDING_SRC = (Source("ita", "s.10(3)(f)", 32), Source("ita", "Second Schedule Part II Sub-Part B item 9", 269), *BAD_DEBT_SRC)
LETTING_SRC = (Source("ita", "s.10(1)(c)", 31), Source("ita", "s.18(1)", 38), Source("ita", "s.18(3)", 38), Source("ita", "s.19(1)", 40))
DISALLOWED = ("depreciation", "entertainment_gifts_and_donations")
DISALLOWED_SRC = (Source("ita", "s.26(1)", 46),)
