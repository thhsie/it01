import re
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any
from it01.form import wanted
from it01.held import DIFFERS, MONTH, UNCHECKED, Case, Line, Payment, Reading, at, typed
from it01.kinds import Paying, Table, paying, picked, spoken
from it01.law import YEAR_STARTS
from it01.tax import ZERO, Facts, Figure, amount, assess, from_json, plain

OUT, WRONG, GONE = "out", "wrong", "no longer read from any document"
ADRIFT = "the balance after this does not agree, so it is left out"
NUMBERED = re.compile(r"payments? (?P<nums>\d+(?:, ?\d+)*)")

@dataclass(frozen=True)
class Tables:
  into: Table
  out: Paying
  lines: dict[str, str]

def tables() -> Tables: return Tables(spoken("labelling"), paying(), dict(wanted().feeds))

@dataclass(frozen=True)
class Asked:
  subject: str
  about: str
  asks: str
  choices: tuple[tuple[str, str], ...]
  document: str|None = None
  headline: str|None = None
  amount: Decimal = ZERO
  adds: tuple[tuple[str, str], ...] = ()
  paid: tuple[str, ...] = ()
  share: bool = False

def year_of(month:str) -> tuple[str, ...]:
  first = int(month[:4]) - (int(month[5:]) < YEAR_STARTS)
  return tuple(f"{first + (YEAR_STARTS - 1 + n) // 12}-{(YEAR_STARTS - 1 + n) % 12 + 1:02d}" for n in range(12))

def yearly(first:str) -> dict[str, str]:
  if not MONTH.fullmatch(first) or int(first[5:]) != YEAR_STARTS:
    raise ValueError(f"an income year starts in month {YEAR_STARTS}, not {first!r}")
  return {"from": first, "to": year_of(first)[-1]}

def months_of(held:Case) -> tuple[str, ...]:
  first = held.year.get("from") or max((p.month for p in held.payments.values() if p.month), default="")
  return year_of(first) if first else ()

def is_inside(p:Payment, months:tuple[str, ...]) -> bool: return p.month is None or p.month in months

def needing(kind:str) -> str: return f"money labelled {kind}"
def costs_of(doc:str, kind:str) -> str: return f"{doc}, paid out as {plain(kind)}"
def trading_in(doc:str) -> str: return f"{doc}, business costs"

def kinds_of(t:Tables, way:str) -> tuple[str, ...]: return picked(t.into) if way == "in" else tuple(t.out.prompt.kinds)

def relabelling(t:Tables, way:str) -> tuple[tuple[str, str], ...]:
  return ((OUT, "leave it out"), *((kind, f"label it {kind}") for kind in kinds_of(t, way)))

def read_as(held:Case, t:Tables, p:Payment) -> str:
  if p.label not in (t.into if p.way == "in" else t.out).prompt.kinds:
    raise ValueError(f"{p.document} holds a payment labelled {p.label}, which the labelling tables do not list")
  if p.way == "in" and p.label in t.into.needs and (instead := held.decisions.get(needing(p.label))) in picked(t.into): return str(instead)
  return p.label

def said_of(held:Case, t:Tables, key:str, p:Payment) -> str|None:
  return said if (said := held.decisions.get(key)) is not None and (said == OUT or said in kinds_of(t, p.way)) else None

def label_of(held:Case, t:Tables, key:str, p:Payment) -> str:
  said = said_of(held, t, key, p)
  return said if said is not None and said != OUT else read_as(held, t, p)

def counted(held:Case, t:Tables, months:tuple[str, ...]) -> list[tuple[str, Payment, str]]:
  ret = []
  for key, p in held.payments.items():
    said = said_of(held, t, key, p)
    if said != OUT and is_inside(p, months) and (said is not None or p.check != DIFFERS): ret.append((key, p, label_of(held, t, key, p)))
  return ret

def worded(p:Payment) -> str: return f"{p.amount:,} paid {p.way} on {p.date}, {p.description}"

def outgoing(amt:Decimal, cnt:int, kind:str, doc:str) -> str:
  return f"{amt:,} paid out in {cnt} payment{'s' if cnt > 1 else ''} that look{'' if cnt > 1 else 's'} like {plain(kind)}, in {doc}"

def claims(held:Case, t:Tables, months:tuple[str, ...]) -> list[Asked]:
  groups:dict[tuple[str, str], list[tuple[str, Decimal]]] = {}
  for key, p, kind in counted(held, t, months):
    if p.way == "out" and kind not in t.out.aside: groups.setdefault((p.document, kind), []).append((key, p.amount))
  ret = []
  for (doc, kind), paid in groups.items():
    total, claim = sum((amt for _, amt in paid), ZERO), (t.out.claims | t.out.business).get(kind)
    if claim: choices = (("yes", f"adds {total:,} to {plain(claim[0])}"), ("no", "adds nothing"))
    else: choices = (("later", "I'll add it later"), ("not", f"this was not for {plain(kind)}"))
    ret.append(Asked(costs_of(doc, kind), outgoing(total, len(paid), kind, doc), claim[1] if claim else t.out.certificates[kind], choices, doc,
                     t.out.headlines.get(kind), total, (("yes", claim[0]),) if claim else (), tuple(k for k, _ in paid), kind in t.out.business))
  return ret

def form_lines(held:Case, t:Tables) -> list[Asked]:
  return [Asked(key, f"{one.amount:,} on the line {one.quote}, in {one.document}", one.asking, one.lines, one.document, amount=one.amount,
                adds=tuple((line, fact) for line, fact in t.lines.items() if line in dict(one.lines))) for key, one in held.lines.items()]

def fits(q:Asked, said:str) -> bool:
  return said in dict(q.choices) or (q.share and (part := typed(said)) is not None and ZERO < part <= q.amount)

def added_by(q:Asked, said:str) -> tuple[str, Decimal]|None:
  if fact := dict(q.adds).get(said): return fact, q.amount
  return (dict(q.adds)["yes"], part) if q.share and said not in dict(q.choices) and (part := typed(said)) is not None else None

def answering(held:Case, q:Asked, parts:dict[str, list[tuple[Decimal, str]]]) -> None:
  if (answer := held.decisions.get(q.subject)) is not None and fits(q, answer) and (hit := added_by(q, answer)):
    parts.setdefault(hit[0], []).append((hit[1], f"answered {q.about}"))

def earned(held:Case, t:Tables, months:tuple[str, ...]) -> dict[str, list[tuple[Decimal, str]]]:
  parts:dict[str, list[tuple[Decimal, str]]] = {}
  by:dict[tuple[str, str], list[Payment]] = {}
  for _, p, kind in counted(held, t, months):
    if p.way == "in" and kind in t.into.feeds: by.setdefault((p.document, kind), []).append(p)
  for (doc, kind), paid in by.items():
    unsure = sum(1 for p in paid if p.check == UNCHECKED)
    said = f"{doc}, {len(paid)} labelled {kind}" + (f", {unsure} unchecked" if unsure else "")
    parts.setdefault(t.into.feeds[kind], []).append((sum((p.amount for p in paid), ZERO), said))
  for key, r in held.readings.items():
    if held.decisions.get(key) != WRONG: parts.setdefault(r.fact, []).append((r.amount, f"{r.document}, {r.quote}"))
  for q in form_lines(held, t): answering(held, q, parts)
  return parts

def is_trading(held:Case, parts:dict[str, list[tuple[Decimal, str]]], elsewhere:bool=False) -> bool:
  return (elsewhere or at(held.given, "business.gross_income") is not None or "business.gross_income" in parts
          or any(held.decisions.get(trading_in(doc)) == "business" for doc in held.documents))

def is_owed(held:Case, q:Asked, trading:bool) -> bool:
  return not q.share or (trading and held.decisions.get(trading_in(q.document or "")) != "not")

def derived(held:Case, t:Tables, trading:bool|None=None) -> dict[str, tuple[Decimal, str]]:
  months = months_of(held)
  parts = earned(held, t, months)
  trading = is_trading(held, parts) if trading is None else trading
  for q in claims(held, t, months):
    if is_owed(held, q, trading): answering(held, q, parts)
  return {fact: (sum((amt for amt, _ in each), ZERO), ", ".join(src for _, src in each)) for fact, each in parts.items()}

def proposals(held:Case, t:Tables) -> tuple[dict[str, Decimal], dict[str, str]]: return proposed_from(held, derived(held, t))

def proposed_from(held:Case, worked:dict[str, tuple[Decimal, str]]) -> tuple[dict[str, Decimal], dict[str, str]]:
  ret, sources = {}, {}
  worked = worked | {fact: (ZERO, GONE) for fact in held.confirmed if fact not in worked}
  for fact, (amt, said) in worked.items():
    if (was := at(held.given, fact)) is not None and amount(held.confirmed.get(fact, str(was))) == amt: continue
    ret[fact], sources[fact] = amt, said
  return ret, sources

def is_given(held:Case, proposed:dict[str, Decimal], name:str) -> bool: return at(held.given, name) is not None or name in proposed

def costing() -> tuple[tuple[str, str], ...]: return (("business", "they are costs of my business"), ("not", "they are not business costs"))

def questions(held:Case, t:Tables, proposed:dict[str, Decimal]) -> list[Asked]:
  months, ret = months_of(held), []
  for key, p in held.payments.items():
    if p.way != "in" or not is_inside(p, months): continue
    if (kind := read_as(held, t, p)) in t.into.asking:
      ret.append(Asked(key, worded(p), t.into.asking[kind], relabelling(t, "in"), p.document, amount=p.amount))
    elif kind in t.into.feeds and p.check == DIFFERS:
      ret.append(Asked(key, worded(p), ADRIFT, relabelling(t, "in"), p.document, "a payment was left out of the totals", p.amount))
  for kind, (fact, asking) in t.into.needs.items():
    came = any(p.way == "in" and p.label == kind and is_inside(p, months) and said_of(held, t, key, p) is None for key, p in held.payments.items())
    if (subject := needing(kind)) in held.decisions or (came and not is_given(held, proposed, fact)):
      choices = tuple((instead, f"label it {instead} instead") for instead in picked(t.into) if instead != kind)
      about = f"money labelled {kind} came in and the case gives no {plain(fact)}"
      ret.append(Asked(subject, about, asking, choices, None, t.into.headlines.get(kind)))
  owed, trading = claims(held, t, months), is_trading(held, earned(held, t, months))
  for doc in dict.fromkeys(q.document for q in owed if q.share and q.document):
    costs = [q for q in owed if q.share and q.document == doc]
    if not trading or trading_in(doc) in held.decisions:
      cnt = sum(len(q.paid) for q in costs)
      ret.append(Asked(trading_in(doc), f"{cnt} payment{'s' if cnt > 1 else ''} in {doc} look{'' if cnt > 1 else 's'} like costs of a business, "
                       "and the case has no business income", "say whether you run a business, even one with no income yet", costing(), doc,
                       "costs of a business with no income yet?"))
    ret += [q for q in costs if is_owed(held, q, trading)]
  return ret + [q for q in owed if not q.share] + form_lines(held, t)

def payment_asked(held:Case, t:Tables, key:str) -> Asked:
  p = held.payments[key]
  return Asked(key, worded(p), "say what this payment was", relabelling(t, p.way), p.document, amount=p.amount)

def subject_of(held:Case, t:Tables, subject:str) -> Asked:
  if q := next((q for q in questions(held, t, proposals(held, t)[0]) if q.subject == subject), None): return q
  if subject in held.payments: return payment_asked(held, t, subject)
  if r := held.readings.get(subject):
    misread = ((WRONG, "this figure was misread"),)
    return Asked(subject, f"{r.amount:,} read from {r.quote}", "say whether this figure was misread", misread, r.document)
  raise ValueError(f"the case asks nothing about {subject}")

def fitted(held:Case, q:Asked, said:str) -> str:
  said = said.strip()
  if q.share and q.paid and (named := NUMBERED.fullmatch(said)):
    nums = [int(n) for n in named["nums"].replace(" ", "").split(",")]
    if len(set(nums)) != len(nums) or not all(1 <= n <= len(q.paid) for n in nums):
      raise ValueError(f"answer {q.subject} naming each of payments 1 to {len(q.paid)} at most once, not {said}")
    return str(sum((held.payments[q.paid[n - 1]].amount for n in nums), ZERO))
  if fits(q, said): return said
  numbered = ", payments by number such as payments 1, 3" if q.share and q.paid else ""
  share = f"{numbered}, or the part that was, from 0.01 to {q.amount:,}" if q.share else ""
  raise ValueError(f"answer {q.subject} with one of: {', '.join(n for n, _ in q.choices)}{share}")

def put(given:dict[str, Any], name:str, amt:Decimal|int|bool) -> dict[str, Any]:
  part, _, rest = name.partition(".")
  return given | {part: (given.get(part) or {}) | {rest: amt} if rest else amt}

def projected(held:Case, worked:dict[str, tuple[Decimal, str]]) -> dict[str, Any]:
  ret = held.given
  for fact, amt in proposed_from(held, worked)[0].items(): ret = put(ret, fact, amt)
  return ret

def balance(given:dict[str, Any]) -> Figure: return next(fig for fig in assess(from_json(Facts, given)) if fig.rule == "balance of tax")

def scoped(held:Case, doc:str|None) -> Case:
  if doc is None: return held
  def own[T:(Payment, Reading, Line)](part:dict[str, T]) -> dict[str, T]: return {k: v for k, v in part.items() if v.document == doc}
  year = yearly(months[0]) if (months := months_of(held)) else held.year
  return replace(held, year=year, payments=own(held.payments), readings=own(held.readings), lines=own(held.lines))

def amounts(worked:dict[str, tuple[Decimal, str]]) -> dict[str, Decimal]: return {fact: amt for fact, (amt, _) in worked.items()}

@dataclass(frozen=True)
class Base:
  worked: dict[str, tuple[Decimal, str]]
  before: Figure|None
  trading: bool
  earning: frozenset[str]

def based(held:Case, t:Tables) -> Base:
  months, worked = months_of(held), derived(held, t)
  try: before = balance(projected(held, worked))
  except ValueError: before = None
  earning = frozenset(doc for doc in held.documents if "business.gross_income" in earned(scoped(held, doc), t, months))
  return Base(worked, before, is_trading(held, earned(held, t, months)), earning)

def priced(held:Case, t:Tables, q:Asked, base:Base) -> dict[str, Figure]:
  ret:dict[str, Figure] = {}
  if base.before is None: return ret
  part, elsewhere = scoped(held, q.document), bool(q.document and base.earning - {q.document})
  months, was = months_of(part), amounts(derived(part, t, base.trading))
  for choice in (c for c, _ in q.choices if c not in t.into.needs):
    said = held.decisions | {q.subject: choice}
    chosen = replace(part, decisions=said)
    if is_trading(chosen, earned(chosen, t, months), elsewhere) == base.trading:
      after = amounts(derived(chosen, t, base.trading))
      moved = {f: (base.worked.get(f, (ZERO, ""))[0] + after.get(f, ZERO) - was.get(f, ZERO), "") for f in (*base.worked, *after)}
    else: moved = derived(replace(held, decisions=said), t)
    try: now = balance(projected(held, moved))
    except ValueError: continue
    ret[choice] = Figure(choice, now.amt - base.before.amt, now.src)
  return ret if any(fig.amt for fig in ret.values()) else {}
