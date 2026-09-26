import re
from dataclasses import MISSING, dataclass, fields
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Any, get_args, get_origin
from it01.law import (CHARGEABLE_SRC, DEPENDANTS, DEPENDANTS_SRC, INTEREST_BAR, INTEREST_SRC, MEDICAL, MEDICAL_SRC, RESIDENT_SRC,
                      Source, CREDITS_SRC, FAIR_SHARE_RATE, FAIR_SHARE_SRC, FAIR_SHARE_THRESHOLD, LOSSES_SRC, ALLOWANCE_SRC, ALLOWANCES,
                      ALLOWANCE_RULES, AllowanceRule, Period, QUARTER_CREDIT_SRC, QUARTER_INCOME_SRC, QUARTER_RELIEF, RATES,
                      MOTOR_VEHICLE_CAP, SMALL_PLANT, AssetKind, Basis, BUSINESS_SRC, DISALLOWED, DISALLOWED_SRC)

ZERO = Decimal(0)
AMOUNT_LIMIT = Decimal(10) ** 15
FIGURE = re.compile(r"(?<![\d.,])(?:\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d{1,3}(?:\.\d{3})+,\d{1,2}"
                    r"|\d{1,3}(?: \d{3})+[.,]\d{1,2}|\d+(?:[.,]\d{1,2})?)(?![.,]?\d)")
DECIMALS = re.compile(r"[.,](\d{1,2})$")
SEPARATOR = re.compile(r"[ ,.]")
JSON_TYPES: dict[Any, tuple[type, ...]] = {bool: (bool,), int: (int,), Decimal: (int, Decimal)}
EXPENSES = ("wages", "professional_expenses", "entertainment_gifts_and_donations", "advertising", "overseas_travel", "interest", "bank_charges",
            "utilities", "rent", "licences_and_taxes", "motor_vehicle_expenses", "repairs", "depreciation", "bad_debts", "other_expenses")

@dataclass(frozen=True)
class Figure:
  rule: str
  amt: Decimal
  src: tuple[Source, ...]

def amount_names(obj:Any) -> tuple[str, ...]: return tuple(f.name for f in fields(obj) if f.type is Decimal)

def is_amount(v:Decimal) -> bool: return v.is_finite() and 0 <= v < AMOUNT_LIMIT and v == v.quantize(Decimal("0.01"))

def to_decimal(text:str) -> Decimal:
  if not (m := DECIMALS.search(text)): return Decimal(SEPARATOR.sub("", text))
  return Decimal(SEPARATOR.sub("", text[:m.start()]) + "." + m.group(1))

def figures(line:str) -> set[Decimal]: return {to_decimal(m) for m in FIGURE.findall(line)}

def amount(raw:object) -> Decimal:
  if not FIGURE.fullmatch(text := str(raw).strip()): raise ValueError(f"not an amount {raw}")
  if not is_amount(value := to_decimal(text)): raise ValueError(f"invalid amount {raw}")
  return value

def check_amounts(obj:Any) -> None:
  for name in amount_names(obj):
    if not (isinstance(v := getattr(obj, name), Decimal) and is_amount(v)): raise ValueError(f"invalid {name} {v}")

@dataclass(frozen=True)
class Asset:
  kind: AssetKind
  cost: Decimal
  allowances_before: Decimal = ZERO

  def __post_init__(self) -> None:
    check_amounts(self)
    if self.allowances_before > self.cost: raise ValueError(f"allowances before {self.allowances_before} exceed cost {self.cost}")
    if self.kind is AssetKind.MOTOR_VEHICLE and self.cost > MOTOR_VEHICLE_CAP: raise ValueError(f"motor vehicle cost {self.cost} not supported yet")

  def allowance(self, part:Decimal) -> Decimal:
    rate, basis, plant = ALLOWANCES[self.kind]
    base = self.cost - self.allowances_before
    if plant and base <= SMALL_PLANT: return base * part
    return min(base, (rate * (self.cost if basis is Basis.COST else base)).quantize(Decimal(1), ROUND_DOWN)) * part

@dataclass(frozen=True)
class Business:
  gross_income: Decimal = ZERO
  cost_of_sales: Decimal = ZERO
  other_income: Decimal = ZERO
  wages: Decimal = ZERO
  professional_expenses: Decimal = ZERO
  entertainment_gifts_and_donations: Decimal = ZERO
  advertising: Decimal = ZERO
  overseas_travel: Decimal = ZERO
  interest: Decimal = ZERO
  bank_charges: Decimal = ZERO
  utilities: Decimal = ZERO
  rent: Decimal = ZERO
  licences_and_taxes: Decimal = ZERO
  motor_vehicle_expenses: Decimal = ZERO
  repairs: Decimal = ZERO
  depreciation: Decimal = ZERO
  bad_debts: Decimal = ZERO
  other_expenses: Decimal = ZERO
  income_not_in_accounts: Decimal = ZERO
  non_allowable_expenses: Decimal = ZERO
  assets: tuple[Asset, ...] = ()

  def __post_init__(self) -> None: check_amounts(self)

  @property
  def gross_profit(self) -> Decimal: return self.gross_income - self.cost_of_sales

  @property
  def net_profit(self) -> Decimal: return self.gross_profit + self.other_income - sum((getattr(self, n) for n in EXPENSES), ZERO)

  @property
  def non_allowable(self) -> Decimal: return self.non_allowable_expenses + sum((getattr(self, n) for n in DISALLOWED), ZERO)

  def net_income(self, part:Decimal) -> Decimal:
    return self.net_profit + self.income_not_in_accounts + self.non_allowable - sum((a.allowance(part) for a in self.assets), ZERO)

@dataclass(frozen=True)
class Facts:
  resident: bool
  dependants: int = 0
  salary: Decimal = ZERO
  taxable_transport_allowance: Decimal = ZERO
  performance_bonus: Decimal = ZERO
  statutory_bonus: Decimal = ZERO
  other_income: Decimal = ZERO
  rent: Decimal = ZERO
  losses_brought_forward: Decimal = ZERO
  resident_dividends: Decimal = ZERO
  housing_loan_interest: Decimal = ZERO
  medical_insurance: Decimal = ZERO
  other_reliefs: Decimal = ZERO
  paye_withheld: Decimal = ZERO
  tax_deducted_at_source: Decimal = ZERO
  quarterly_tax_paid: Decimal = ZERO
  business: Business = Business()
  period: Period = Period.YEAR

  def __post_init__(self) -> None:
    if self.dependants < 0: raise ValueError(f"invalid dependants {self.dependants}")
    check_amounts(self)
    if self.period is Period.YEAR: return
    if held := sorted(n for n in AMOUNTS if n not in QUARTERLY and getattr(self, n)): raise ValueError(f"a quarter does not take {held}")

  @property
  def emoluments(self) -> Decimal: return self.salary + self.taxable_transport_allowance + self.performance_bonus + self.statutory_bonus

AMOUNTS = amount_names(Facts)
PLACES = (*AMOUNTS, *(f"business.{n}" for n in amount_names(Business)))
QUARTERLY = ("rent", "losses_brought_forward", "tax_deducted_at_source")

def from_json[T:(Facts, Business, Asset)](cls:type[T], raw:Any) -> T:
  name = cls.__name__.lower()
  if not isinstance(raw, dict): raise ValueError(f"{name} must be a JSON object")
  types = {f.name: f.type for f in fields(cls)}
  if unknown := sorted(set(raw) - set(types)): raise ValueError(f"unknown {name} {unknown}")
  if missing := sorted(f.name for f in fields(cls) if f.default is MISSING and f.name not in raw): raise ValueError(f"missing {name} {missing}")
  vals: dict[str, Any] = {}
  for k, v in raw.items():
    if get_origin(t := types[k]) is tuple:
      if not isinstance(v, list): raise ValueError(f"{k} must be a JSON list")
      vals[k] = tuple(from_json(get_args(t)[0], x) for x in v)
    elif t is Business: vals[k] = from_json(Business, v)
    elif isinstance(t, type) and issubclass(t, Enum):
      if (m := {x.name.lower(): x for x in t}.get(v)) is None: raise ValueError(f"unknown {k} {v}")
      vals[k] = m
    elif type(v) not in JSON_TYPES[t]: raise ValueError(f"invalid {k} {v} of type {type(v).__name__}")
    else: vals[k] = Decimal(v) if t is Decimal else v
  return cls(**vals)

def rupees(x:Decimal) -> Decimal: return x.quantize(Decimal(1), ROUND_HALF_UP)

def net_income_and_losses(f:Facts) -> tuple[Decimal, Decimal]:
  business = f.business.net_income(ALLOWANCE_RULES[f.period].part)
  other = f.other_income + f.rent + max(ZERO, business)
  used = min(other, losses := f.losses_brought_forward + max(ZERO, -business))
  return f.emoluments + other - used, losses - used

def chargeable_income(f:Facts) -> Figure:
  amt, src = net_income_and_losses(f)[0], list(CHARGEABLE_SRC + RESIDENT_SRC + LOSSES_SRC)
  if f.period is Period.QUARTER: src += QUARTER_INCOME_SRC
  if f.resident:
    cnt = min(f.dependants, len(DEPENDANTS) - 1)
    if f.period is Period.QUARTER: amt, src = amt - DEPENDANTS[cnt] * QUARTER_RELIEF, src + list(DEPENDANTS_SRC)
    else:
      interest = f.housing_loan_interest if amt + f.resident_dividends <= INTEREST_BAR else ZERO
      amt -= DEPENDANTS[cnt] + min(f.medical_insurance, MEDICAL[cnt]) + interest + f.other_reliefs
      src += DEPENDANTS_SRC + MEDICAL_SRC + INTEREST_SRC
  return Figure("chargeable income", rupees(max(ZERO, amt)), tuple(src))

def income_tax(chargeable:Decimal, period:Period) -> Figure:
  whole = chargeable.is_finite() and chargeable >= 0 and chargeable == chargeable.to_integral_value()
  if not whole: raise ValueError(f"invalid chargeable income {chargeable}")
  bands, src = RATES[period]
  ret, lo = ZERO, ZERO
  for width, rate in bands: ret, lo = ret + (max(ZERO, min(chargeable - lo, width)) * rate).quantize(Decimal(1), ROUND_DOWN), lo + width
  return Figure("income tax", ret, src)

def business_figures(b:Business, rule:AllowanceRule) -> tuple[Figure, ...]:
  each = tuple(Figure(f"{rule.wording} {a.kind.name.lower().replace('_', ' ')}", a.allowance(rule.part), ALLOWANCE_SRC + rule.src) for a in b.assets)
  return (Figure("gross profit", b.gross_profit, BUSINESS_SRC), Figure("net profit per accounts", b.net_profit, BUSINESS_SRC),
          Figure("non-allowable expenses", b.non_allowable, DISALLOWED_SRC), *each,
          Figure("net income from business", b.net_income(rule.part), BUSINESS_SRC + DISALLOWED_SRC + ALLOWANCE_SRC + rule.src))

def assess(f:Facts) -> tuple[Figure, ...]:
  ci = chargeable_income(f)
  tax = income_tax(ci.amt, f.period)
  losses = Figure("losses carried forward", net_income_and_losses(f)[1], LOSSES_SRC)
  ret:tuple[Figure, ...]
  if f.period is Period.QUARTER:
    paid = Figure("tax already paid", f.tax_deducted_at_source, QUARTER_CREDIT_SRC)
    ret = (ci, tax, paid, Figure("balance of tax", tax.amt - paid.amt, tax.src + QUARTER_CREDIT_SRC), losses)
    return ret if (b := f.business) == Business() else (*ret, *business_figures(b, ALLOWANCE_RULES[f.period]))
  share = Figure("fair share contribution", rupees(max(ZERO, ci.amt + f.resident_dividends - FAIR_SHARE_THRESHOLD) * FAIR_SHARE_RATE), FAIR_SHARE_SRC)
  total = Figure("total tax", tax.amt + share.amt, tax.src + share.src)
  paid = Figure("tax already paid", f.paye_withheld + f.tax_deducted_at_source + f.quarterly_tax_paid, CREDITS_SRC)
  balance = Figure("balance of tax", total.amt - paid.amt, total.src + CREDITS_SRC)
  ret = (ci, tax, share, total, paid, balance, losses)
  return ret if (b := f.business) == Business() else (*ret, *business_figures(b, ALLOWANCE_RULES[f.period]))
