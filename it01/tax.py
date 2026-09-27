import re
from dataclasses import MISSING, dataclass, fields
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Any, get_args, get_origin
from it01.law import (CHARGEABLE_SRC, DEPENDANTS, DEPENDANTS_SRC, INTEREST_BAR, INTEREST_SRC, MEDICAL, MEDICAL_SRC, RESIDENT_SRC,
                      Source, CREDITS_SRC, FAIR_SHARE_RATE, FAIR_SHARE_SRC, FAIR_SHARE_THRESHOLD, LOSSES_SRC, ALLOWANCE_SRC, ALLOWANCES,
                      ALLOWANCE_RULES, AllowanceRule, Period, QUARTER_CREDIT_SRC, QUARTER_INCOME_SRC, QUARTER_RELIEF, RATES,
                      MOTOR_VEHICLE_CAP, SMALL_PLANT, AssetKind, Basis, BUSINESS_SRC, DISALLOWED, DISALLOWED_SRC,
                      ADDITION, ADDITION_SRC, CAPPED, RETIRED_EMOLUMENTS, TERTIARY, TERTIARY_CHILDREN, TERTIARY_TUITION, TERTIARY_SRC,
                      TERTIARY_YEARS, Addition, LETTING_SRC, HEADS, ABROAD, LENDING_EXEMPT, LENDING_SRC, BAD_DEBT_SRC, DEPENDANT_LIMITS,
                      DEPENDANT_INCOME_SRC)

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

def summed(pairs:list[tuple[str, Decimal]]) -> dict[str, Decimal]:
  ret:dict[str, Decimal] = {}
  for name, amt in pairs: ret[name] = ret.get(name, ZERO) + amt
  return ret

def is_amount(v:Decimal) -> bool: return v.is_finite() and 0 <= v < AMOUNT_LIMIT and v == v.quantize(Decimal("0.01"))

def to_decimal(text:str) -> Decimal:
  if not (m := DECIMALS.search(text)): return Decimal(SEPARATOR.sub("", text))
  return Decimal(SEPARATOR.sub("", text[:m.start()]) + "." + m.group(1))

def figures(line:str) -> set[Decimal]: return {to_decimal(m) for m in FIGURE.findall(line)}

def amount(raw:object) -> Decimal:
  if not FIGURE.fullmatch(text := str(raw).strip()): raise ValueError(f"not an amount {raw}")
  if not is_amount(value := to_decimal(text)): raise ValueError(f"invalid amount {raw}")
  return value

def is_held(v:object, default:object) -> bool: return any(v) if isinstance(v, tuple) else v != default

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
class Letting:
  repairs: Decimal = ZERO
  interest: Decimal = ZERO
  syndic_fees: Decimal = ZERO
  other_expenses: Decimal = ZERO
  assets: tuple[Asset, ...] = ()

  def __post_init__(self) -> None: check_amounts(self)

  def expenses(self, part:Decimal) -> Decimal:
    return self.repairs + self.interest + self.syndic_fees + self.other_expenses + sum((a.allowance(part) for a in self.assets), ZERO)

@dataclass(frozen=True)
class Farming:
  gross_income: Decimal = ZERO
  labour: Decimal = ZERO
  rent: Decimal = ZERO
  fertilizers_and_pesticides: Decimal = ZERO
  motor_vehicle_expenses: Decimal = ZERO
  other_expenses: Decimal = ZERO

  def __post_init__(self) -> None: check_amounts(self)

  @property
  def net(self) -> Decimal:
    return self.gross_income - self.labour - self.rent - self.fertilizers_and_pesticides - self.motor_vehicle_expenses - self.other_expenses

@dataclass(frozen=True)
class Tuition:
  gross_income: Decimal = ZERO
  expenses: Decimal = ZERO

  def __post_init__(self) -> None: check_amounts(self)

  @property
  def net(self) -> Decimal: return max(ZERO, self.gross_income - self.expenses)

@dataclass(frozen=True)
class Lending:
  interest: Decimal = ZERO
  bad_debts: Decimal = ZERO

  def __post_init__(self) -> None: check_amounts(self)

  @property
  def exempt(self) -> Decimal: return (self.interest * LENDING_EXEMPT).quantize(Decimal("0.01"), ROUND_DOWN)

  @property
  def taxable(self) -> Decimal: return max(ZERO, self.interest - self.exempt - self.bad_debts)

  @property
  def carried(self) -> Decimal: return max(ZERO, self.bad_debts - self.interest)

@dataclass(frozen=True)
class Dependant:
  income: Decimal
  exempt: Decimal = ZERO
  emoluments: Decimal = ZERO

  def __post_init__(self) -> None:
    check_amounts(self)
    if self.exempt + self.emoluments > self.income: raise ValueError(f"exempt income and emoluments exceed the income {self.income}")

  @property
  def other(self) -> Decimal: return self.income - self.exempt - self.emoluments

@dataclass(frozen=True)
class Student:
  abroad: bool
  undergraduate: bool
  tuition: Decimal
  year: int

  def __post_init__(self) -> None:
    check_amounts(self)
    if self.year < 1: raise ValueError(f"invalid year {self.year}")

  @property
  def is_allowed(self) -> bool: return self.year <= TERTIARY_YEARS and (self.abroad or not self.undergraduate or self.tuition >= TERTIARY_TUITION)

@dataclass(frozen=True)
class Facts:
  resident: bool
  dependants: int = 0
  salary: Decimal = ZERO
  taxable_transport_allowance: Decimal = ZERO
  performance_bonus: Decimal = ZERO
  statutory_bonus: Decimal = ZERO
  other_income: Decimal = ZERO
  basic_retirement_pension: Decimal = ZERO
  state_pension: Decimal = ZERO
  social_retirement_benefit: Decimal = ZERO
  taxable_interest: Decimal = ZERO
  royalty: Decimal = ZERO
  premium: Decimal = ZERO
  annuity: Decimal = ZERO
  charges: Decimal = ZERO
  other_source: Decimal = ZERO
  foreign_dividend: Decimal = ZERO
  foreign_rent: Decimal = ZERO
  foreign_interest: Decimal = ZERO
  foreign_other: Decimal = ZERO
  rent: Decimal = ZERO
  letting: Letting = Letting()
  farming: Farming = Farming()
  tuition: Tuition = Tuition()
  lending: Lending = Lending()
  losses_brought_forward: Decimal = ZERO
  resident_dividends: Decimal = ZERO
  housing_loan_interest: Decimal = ZERO
  dependant_income: tuple[Dependant, ...] = ()
  medical_insurance: tuple[Decimal, ...] = ()
  other_reliefs: Decimal = ZERO
  additional_deduction: Addition = Addition.NONE
  students: tuple[Student, ...] = ()
  school_fees: tuple[Decimal, ...] = ()
  electronic_donations: Decimal = ZERO
  pension_contributions: Decimal = ZERO
  carer_wages: Decimal = ZERO
  paye_withheld: Decimal = ZERO
  tax_deducted_at_source: Decimal = ZERO
  quarterly_tax_paid: Decimal = ZERO
  business: Business = Business()
  period: Period = Period.YEAR

  def __post_init__(self) -> None:
    if self.dependants < 0: raise ValueError(f"invalid dependants {self.dependants}")
    check_amounts(self)
    for name in ("medical_insurance", "school_fees"):
      if (bad := next((v for v in getattr(self, name) if not is_amount(v)), None)) is not None: raise ValueError(f"invalid {name} {bad}")
    if len(self.medical_insurance) > (most := min(self.dependants, len(MEDICAL) - 1) + 1):
      raise ValueError(f"medical_insurance names {len(self.medical_insurance)} people, at most {most} can be insured")
    if (children := len(self.school_fees) + len(self.students)) > self.dependants:
      raise ValueError(f"school_fees and students name {children} children, more than the {self.dependants} dependants")
    if len(self.dependant_income) > (most := min(self.dependants, len(DEPENDANT_LIMITS))):
      raise ValueError(f"dependant_income names {len(self.dependant_income)} dependants, at most {most} can have income")
    for idx, (one, limit) in enumerate(zip(self.dependant_income, DEPENDANT_LIMITS), 1):
      if one.income > limit: raise ValueError(f"dependant {idx} has {one.income:,} of income, above {limit:,}, so cannot be claimed")
    if not self.resident and self.dependant_income: raise ValueError("a non-resident cannot claim dependant_income")
    if len(self.students) > TERTIARY_CHILDREN:
      raise ValueError(f"students names {len(self.students)} children, at most {TERTIARY_CHILDREN} can be claimed")
    if not self.resident and (abroad := [n for n in ABROAD if getattr(self, n)]):
      raise ValueError(f"a non-resident cannot have income from abroad {abroad}")
    if self.period is Period.YEAR: return
    held = sorted(f.name for f in fields(self) if f.name not in QUARTER_TAKES and is_held(getattr(self, f.name), f.default))
    if held: raise ValueError(f"a quarter does not take {held}")

  @property
  def emoluments(self) -> Decimal: return self.salary + self.taxable_transport_allowance + self.performance_bonus + self.statutory_bonus

AMOUNTS = amount_names(Facts)
PLACES = (*AMOUNTS, *(f"business.{n}" for n in amount_names(Business)))
QUARTER_TAKES = ("resident", "dependants", "rent", "losses_brought_forward", "tax_deducted_at_source", "business", "period")

def plain(name:str) -> str: return name.replace(".", " ").replace("_", " ")

RECORDS = (Business, Letting, Farming, Tuition, Lending)

def from_json[T:(Facts, Business, Asset, Student, Dependant, Letting, Farming, Tuition, Lending)](cls:type[T], raw:Any) -> T:
  name = cls.__name__.lower()
  if not isinstance(raw, dict): raise ValueError(f"{name} must be a JSON object")
  types = {f.name: f.type for f in fields(cls)}
  if unknown := sorted(set(raw) - set(types)): raise ValueError(f"unknown {name} {unknown}")
  if missing := sorted(f.name for f in fields(cls) if f.default is MISSING and f.name not in raw): raise ValueError(f"missing {name} {missing}")
  vals: dict[str, Any] = {}
  for k, v in raw.items():
    if get_origin(t := types[k]) is tuple:
      if not isinstance(v, list): raise ValueError(f"{k} must be a JSON list")
      if (item := get_args(t)[0]) is not Decimal: vals[k] = tuple(from_json(item, x) for x in v)
      elif (bad := next((x for x in v if type(x) not in JSON_TYPES[Decimal]), None)) is not None:
        raise ValueError(f"invalid {k} {bad} of type {type(bad).__name__}")
      else: vals[k] = tuple(Decimal(x) for x in v)
    elif t in RECORDS: vals[k] = from_json(t, v)
    elif isinstance(t, type) and issubclass(t, Enum):
      if (m := {x.name.lower(): x for x in t}.get(v)) is None: raise ValueError(f"unknown {k} {v}")
      vals[k] = m
    elif type(v) not in JSON_TYPES[t]: raise ValueError(f"invalid {k} {v} of type {type(v).__name__}")
    else: vals[k] = Decimal(v) if t is Decimal else v
  return cls(**vals)

def rupees(x:Decimal) -> Decimal: return x.quantize(Decimal(1), ROUND_HALF_UP)

def net_rent(f:Facts, part:Decimal) -> Decimal: return f.rent - f.letting.expenses(part)

def net_income_and_losses(f:Facts) -> tuple[Decimal, Decimal]:
  business = f.business.net_income(part := ALLOWANCE_RULES[f.period].part)
  letting = net_rent(f, part)
  signed = (letting, business, f.farming.net)
  own = f.tuition.net + f.lending.taxable + sum((max(ZERO, x) for x in signed), ZERO)
  other = f.other_income + sum((getattr(f, n) for n in HEADS), ZERO) + own + sum((d.other for d in f.dependant_income), ZERO)
  used = min(other, losses := f.losses_brought_forward + sum((max(ZERO, -x) for x in signed), ZERO))
  return f.emoluments + sum((d.emoluments for d in f.dependant_income), ZERO) + other - used, losses - used

def reliefs(f:Facts) -> list[tuple[Decimal, tuple[Source, ...]]]:
  ret:list[tuple[Decimal, tuple[Source, ...]]] = []
  for name, (cap, cited) in CAPPED.items():
    paid = held if isinstance(held := getattr(f, name), tuple) else (held,)
    if any(paid): ret.append((sum((min(one, cap) for one in paid), ZERO), cited))
  if f.students: ret.append((TERTIARY * sum(1 for s in f.students if s.is_allowed), TERTIARY_SRC))
  if (addition := f.additional_deduction) is not Addition.NONE:
    trading = (f.business, f.farming, f.tuition, f.lending) != (Business(), Farming(), Tuition(), Lending())
    allowed = addition is Addition.DISABLED or (f.emoluments <= RETIRED_EMOLUMENTS and not trading)
    ret.append((ADDITION if allowed else ZERO, ADDITION_SRC))
  return ret

def chargeable_income(f:Facts) -> Figure:
  amt, src = net_income_and_losses(f)[0], list(CHARGEABLE_SRC + RESIDENT_SRC + LOSSES_SRC)
  if f.dependant_income: src += DEPENDANT_INCOME_SRC
  src += list(dict.fromkeys(cited for n, heads in HEADS.items() if getattr(f, n) for cited in heads))
  if f.period is Period.QUARTER: src += QUARTER_INCOME_SRC
  if f.resident:
    cnt = min(f.dependants, len(DEPENDANTS) - 1)
    if f.period is Period.QUARTER: amt, src = amt - DEPENDANTS[cnt] * QUARTER_RELIEF, src + list(DEPENDANTS_SRC)
    else:
      interest = f.housing_loan_interest if amt + f.resident_dividends <= INTEREST_BAR else ZERO
      medical = sum((min(paid, cap) for paid, cap in zip(f.medical_insurance, MEDICAL)), ZERO)
      amt -= DEPENDANTS[cnt] + medical + interest + f.other_reliefs
      src += DEPENDANTS_SRC + MEDICAL_SRC + INTEREST_SRC
      for relief, cited in reliefs(f):
        amt, src = amt - relief, src + list(cited)
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
  if f.letting != Letting():
    ret = (*ret, Figure("net income from rent", net_rent(f, ALLOWANCE_RULES[f.period].part), LETTING_SRC + ALLOWANCE_SRC))
  if f.farming != Farming(): ret = (*ret, Figure("net income from agriculture", f.farming.net, BUSINESS_SRC))
  if f.tuition != Tuition(): ret = (*ret, Figure("net income from private tuition", f.tuition.net, BUSINESS_SRC))
  if f.lending != Lending():
    ret = (*ret, Figure("net interest from peer to peer lending", f.lending.taxable, LENDING_SRC),
           Figure("peer to peer bad debts carried forward", f.lending.carried, BAD_DEBT_SRC))
  return ret if (b := f.business) == Business() else (*ret, *business_figures(b, ALLOWANCE_RULES[f.period]))
