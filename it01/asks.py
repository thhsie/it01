import re
from collections import Counter
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from it01.form import wanted
from it01.held import DIFFERS, MONTH, UNCHECKED, Case, Line, Payment, Reading, at, typed
from it01.kinds import Paying, Table, paying, picked, spoken
from it01.law import EARLIER_MONTHS, YEAR_STARTS
from it01.tax import ZERO, Facts, Figure, amount, assess, from_json, plain

OUT, SAME, WRONG, EACH, GONE = "out", "same", "wrong", "each", "no longer read from any document"
ADRIFT = "the balance after this does not agree, so it is left out"
NUMBERED = re.compile(r"payments? (?P<nums>\d+(?:, ?\d+)*)")
SHARE = re.compile(r"share (?P<part>\S+) of (?P<whole>\S+)")

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
  closes: str|None = None
  trade: bool = False
  payees: tuple[str, ...] = ()
  amounts: tuple[Decimal, ...] = ()
  months: tuple[str, ...] = ()

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

def uncovered(held:Case, months:tuple[str, ...]) -> list[str]:
  dated = [[p.month for p in held.payments.values() if p.document == doc and p.month] for doc in held.documents]
  if not held.year or not (spans := [(min(one), max(one)) for one in dated if one]): return []
  return [m for m in months if not any(first <= m <= last for first, last in spans)]

def unread(missing:list[str]) -> list[Asked]:
  if not missing: return []
  return [Asked(f"months no statement covers, {', '.join(missing)}", f"no statement covers {', '.join(missing)}",
               "money paid in those months is not counted. Add the statements, or say your accounts had no payments then",
               (("later", "I'll add the statements"), ("none", "my accounts had no payments in those months")), None,
               "a statement seems to be missing", months=tuple(missing))]

def needing(kind:str) -> str: return f"money labelled {kind}"
def costs_of(doc:str, kind:str, way:str="out") -> str: return f"{doc}, paid {way} as {plain(kind)}"
def trading_in(doc:str) -> str: return f"{doc}, business costs"

def kinds_of(t:Tables, way:str) -> tuple[str, ...]: return picked(t.into) if way == "in" else tuple(t.out.prompt.kinds)

def relabelling(t:Tables, way:str) -> tuple[tuple[str, str], ...]:
  return ((OUT, "leave it out"), *((kind, f"label it {kind}") for kind in kinds_of(t, way)))

def read_as(held:Case, t:Tables, p:Payment) -> str:
  if p.label not in (t.into if p.way == "in" else t.out).prompt.kinds:
    raise ValueError(f"{p.document} holds a payment labelled {p.label}, which the labelling tables do not list")
  if p.way == "in" and p.label in t.into.needs and (instead := held.decisions.get(needing(p.label))) in picked(t.into): return str(instead)
  return p.label

def is_named(word:str) -> bool: return not any(c.isdigit() for c in word) or (word.isdigit() and len(word) >= 6)

def payer(p:Payment) -> str: return " ".join(w for w in p.description.upper().split() if is_named(w))

def alike(p:Payment) -> str: return f"payments paid {p.way} worded like {payer(p)}"

def remembered(held:Case, t:Tables, p:Payment) -> str|None:
  return said if payer(p) and (said := held.decisions.get(alike(p))) is not None and (said == OUT or said in kinds_of(t, p.way)) else None

def rule_of(held:Case, t:Tables, key:str, p:Payment) -> str|None:
  return alike(p) if key not in held.decisions and remembered(held, t, p) is not None else None

def said_of(held:Case, t:Tables, key:str, p:Payment) -> str|None:
  if (said := held.decisions.get(key)) is not None and (said in (OUT, SAME) or said in kinds_of(t, p.way)): return said
  return remembered(held, t, p)

def label_of(held:Case, t:Tables, key:str, p:Payment) -> str:
  said = said_of(held, t, key, p)
  return said if said is not None and said not in (OUT, SAME) else read_as(held, t, p)

def is_counting(p:Payment, said:str|None, months:tuple[str, ...]) -> bool:
  return said != OUT and is_inside(p, months) and (said not in (None, SAME) or p.check != DIFFERS)

Signed = tuple[str, Decimal, str, str]

def signed(p:Payment) -> Signed: return p.way, p.amount, p.date, " ".join(p.description.split()).lower()

def copies(held:Case, t:Tables, months:tuple[str, ...]) -> dict[str, str]:
  first:dict[Signed, str] = {}
  kept, seen = Counter[tuple[Signed, str]](), Counter[tuple[Signed, str]]()
  ret = {}
  for key, p in held.payments.items():
    sig = signed(p)
    seen[sig, p.document] += 1
    if (doc := first.get(sig)) and doc != p.document and seen[sig, p.document] <= kept[sig, doc]: ret[key] = doc
    elif is_counting(p, said_of(held, t, key, p), months):
      first.setdefault(sig, p.document)
      kept[sig, p.document] += 1
  return ret

def is_dropped(said:str|None, key:str, copied:dict[str, str]) -> bool: return said == OUT or (key in copied and said in (None, SAME))

Rows = list[tuple[str, Payment, str]]

def kept_rows(held:Case, t:Tables, months:tuple[str, ...]) -> Rows:
  copied = copies(held, t, months)
  return [(key, p, label_of(held, t, key, p)) for key, p in held.payments.items()
          if not is_dropped(said := said_of(held, t, key, p), key, copied) and is_counting(p, said, months)]

def this_year(key:str) -> str: return f"{key}, for this income year"

def is_earlier(held:Case, t:Tables, key:str, kind:str, p:Payment, months:tuple[str, ...]) -> bool:
  return p.way == "out" and kind in t.out.earlier and p.month in months[:EARLIER_MONTHS] and this_year(key) not in held.decisions

def earlier(held:Case, t:Tables, months:tuple[str, ...]) -> dict[str, str]:
  return {key: t.out.earlier[kind] for key, p, kind in kept_rows(held, t, months) if is_earlier(held, t, key, kind, p, months)}

def counted(held:Case, t:Tables, months:tuple[str, ...]) -> Rows:
  return [(key, p, kind) for key, p, kind in kept_rows(held, t, months) if not is_earlier(held, t, key, kind, p, months)]

def kept_asks(held:Case, t:Tables) -> list[Asked]:
  return [Asked(this_year(key), worded(p := held.payments[key]), why, (("yes", "it paid tax for this income year"),), p.document, amount=p.amount)
          for key, why in earlier(held, t, months_of(held)).items()]

def twice(t:Tables, way:str, doc:str) -> tuple[tuple[str, str], ...]:
  return ((SAME, f"it is the same payment as in {doc}"), *relabelling(t, way))

def worded(p:Payment) -> str: return f"{p.amount:,} paid {p.way} on {p.date}, {p.description}"

def outgoing(amt:Decimal, cnt:int, kind:str, doc:str, way:str) -> str:
  return f"{amt:,} paid {way} in {cnt} payment{'s' if cnt > 1 else ''} that look{'' if cnt > 1 else 's'} like {plain(kind)}, in {doc}"

def payee_of(p:Payment, kind:str) -> str: return f"{alike(p)}, as {plain(kind)}"

def claims(t:Tables, rows:Rows) -> list[Asked]:
  groups:dict[tuple[str, str, str], list[tuple[str, Payment]]] = {}
  for key, p, kind in rows:
    is_asked = kind in t.into.business if p.way == "in" else kind not in t.out.aside
    if is_asked: groups.setdefault((p.document, p.way, kind), []).append((key, p))
  ret = []
  for (doc, way, kind), members in groups.items():
    paid = [(key, p.amount) for key, p in members]
    trading = t.into.business if way == "in" else t.out.business
    picking = trading | (t.out.picks if way == "out" else {})
    claimable, headlines = picking | (t.out.claims if way == "out" else {}), (t.into if way == "in" else t.out).headlines
    total, claim = sum((amt for _, amt in paid), ZERO), claimable.get(kind)
    asking, closes = (claim[1], None) if claim else t.out.certificates[kind]
    payees = tuple(payee_of(p, kind) if claim and payer(p) and not (way == "out" and kind in t.out.picks) else "" for _, p in members)
    holds = ", and counts for other statements with the same payees" if any(payees) else ""
    if claim: choices = (("yes", f"adds {total:,} to {plain(claim[0])}{holds}"), ("no", f"adds nothing{holds}"))
    else: choices = (("later", "I'll add it later"), ("not", f"this was not for {plain(kind)}"))
    ret.append(Asked(costs_of(doc, kind, way), outgoing(total, len(paid), kind, doc, way), asking, choices, doc, headlines.get(kind), total,
                     (("yes", claim[0]),) if claim else (), tuple(k for k, _ in paid), kind in picking, closes, trade=kind in trading,
                     payees=payees, amounts=tuple(amt for _, amt in paid)))
  return ret

def form_lines(held:Case, t:Tables) -> list[Asked]:
  return [Asked(key, f"{one.amount:,} on the line {one.quote}, in {one.document}", one.asking, one.lines, one.document, amount=one.amount,
                adds=tuple((line, fact) for line, fact in t.lines.items() if line in dict(one.lines))) for key, one in held.lines.items()]

def chosen_in(q:Asked, said:str) -> tuple[int, ...]|None:
  if not q.share or (nums := numbers(said)) is None: return None
  return tuple(nums) if len(set(nums)) == len(nums) and all(1 <= n <= len(q.paid) for n in nums) else None

def share_of(q:Asked, said:str) -> Decimal|None:
  if (nums := chosen_in(q, said)) is not None: return sum((q.amounts[n - 1] for n in nums), ZERO)
  return part if q.share and (part := typed(said)) is not None and ZERO < part <= q.amount else None

def fits(q:Asked, said:str) -> bool: return said in dict(q.choices) or share_of(q, said) is not None

def added_by(q:Asked, said:str) -> tuple[str, Decimal]|None:
  if fact := dict(q.adds).get(said): return fact, q.amount
  return (dict(q.adds)["yes"], part) if said not in dict(q.choices) and (part := share_of(q, said)) is not None else None

def carried(held:Case, q:Asked) -> str|None:
  if not q.payees or not all(q.payees): return None
  if not (said := {held.decisions.get(payee) for payee in q.payees}) <= {"yes", "no"}:
    if not q.share or len(said) != 1 or not (got := SHARE.fullmatch(said.pop() or "")): return None
    if (part := typed(got["part"])) is None or not (whole := typed(got["whole"])): return None
    amt = (q.amount * part / whole).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return str(amt) if ZERO < amt <= q.amount else None
  if len(said) == 1: return said.pop()
  chosen = [str(n) for n, payee in enumerate(q.payees, 1) if held.decisions[payee] == "yes"]
  return f"payments {', '.join(chosen)}" if q.share else None

def said_to(held:Case, q:Asked) -> str|None:
  if (said := held.decisions.get(q.subject)) is not None: return said if fits(q, said) else None
  return carried(held, q)

Parts = dict[str, list[tuple[Decimal, str, tuple[str, ...]]]]

def behind(q:Asked, said:str) -> tuple[str, ...]:
  if (nums := chosen_in(q, said)) is not None: return tuple(q.paid[n - 1] for n in nums)
  return q.paid if said in dict(q.adds) and q.paid else (q.subject,)

def answering(held:Case, q:Asked, parts:Parts) -> None:
  if (answer := said_to(held, q)) is not None and (hit := added_by(q, answer)):
    said = f"answered {q.about}" if q.subject in held.decisions else f"carried from {', '.join(dict.fromkeys(q.payees))}"
    parts.setdefault(hit[0], []).append((hit[1], said, behind(q, answer)))

def earned(held:Case, t:Tables, rows:Rows) -> Parts:
  parts:Parts = {}
  by:dict[tuple[str, str], list[tuple[str, Payment]]] = {}
  for key, p, kind in rows:
    if p.way == "in" and kind in t.into.feeds: by.setdefault((p.document, kind), []).append((key, p))
  for (doc, kind), paid in by.items():
    unsure = sum(1 for _, p in paid if p.check == UNCHECKED)
    said = f"{doc}, {len(paid)} labelled {kind}" + (f", {unsure} unchecked" if unsure else "")
    parts.setdefault(t.into.feeds[kind], []).append((sum((p.amount for _, p in paid), ZERO), said, tuple(key for key, _ in paid)))
  for key, r in held.readings.items():
    if held.decisions.get(key) != WRONG: parts.setdefault(r.fact, []).append((r.amount, f"{r.document}, {r.quote}", (key,)))
  for q in form_lines(held, t): answering(held, q, parts)
  return parts

def is_trading(held:Case, parts:Parts, elsewhere:bool=False) -> bool:
  return (elsewhere or at(held.given, "business.gross_income") is not None or "business.gross_income" in parts
          or any(held.decisions.get(trading_in(doc)) == "business" for doc in held.documents))

def is_owed(held:Case, q:Asked, trading:bool) -> bool:
  return not q.trade or (trading and held.decisions.get(trading_in(q.document or "")) != "not")

def claimed(held:Case, t:Tables, rows:Rows, parts:Parts, trading:bool) -> Parts:
  for q in claims(t, rows):
    if is_owed(held, q, trading): answering(held, q, parts)
  return parts

def totals(parts:Parts) -> dict[str, tuple[Decimal, str]]:
  return {fact: (sum((amt for amt, _, _ in each), ZERO), ", ".join(src for _, src, _ in each)) for fact, each in parts.items()}

def worked_out(held:Case, t:Tables, rows:Rows, parts:Parts, trading:bool) -> dict[str, tuple[Decimal, str]]:
  return totals(claimed(held, t, rows, parts, trading))

def parts_of(held:Case, t:Tables, trading:bool|None=None) -> Parts:
  rows = counted(held, t, months_of(held))
  parts = earned(held, t, rows)
  return claimed(held, t, rows, parts, is_trading(held, parts) if trading is None else trading)

def derived(held:Case, t:Tables, trading:bool|None=None) -> dict[str, tuple[Decimal, str]]: return totals(parts_of(held, t, trading))

def evidence(held:Case, t:Tables) -> dict[str, list[str]]:
  return {fact: [key for _, _, keys in each for key in keys] for fact, each in parts_of(held, t).items()}

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

def together(held:Case, t:Tables, subject:str, members:list[tuple[str, Payment, str]]) -> list[Asked]:
  if len(members) < 2 or held.decisions.get(subject) == EACH:
    return [Asked(key, worded(p), t.into.asking[kind], relabelling(t, "in"), p.document, amount=p.amount) for key, p, kind in members]
  total = sum((p.amount for _, p, _ in members), ZERO)
  about = f"{len(members)} payments paid in worded like {payer(members[0][1])}, {total:,} in all"
  asks = "say what these payments were. The answer counts for each payment listed"
  return [Asked(subject, about, asks, (*relabelling(t, "in"), (EACH, "they differ, so ask about each one")), None,
                "payments worded alike", total, paid=tuple(key for key, _, _ in members))]

def is_alike(q:Asked) -> bool: return EACH in dict(q.choices)

def is_listed(q:Asked) -> bool: return q.share or is_alike(q)

def decided(q:Asked, said:str) -> dict[str, str]: return dict.fromkeys(q.paid, said) if is_alike(q) and said != EACH else {q.subject: said}

def for_payees(q:Asked, said:str) -> dict[str, str|None]:
  if said in ("yes", "no"): return {payee: said for payee in q.payees if payee}
  seen:dict[str, set[bool]] = {}
  if (chosen := numbers(said)) is not None:
    for n, payee in enumerate(q.payees, 1):
      if payee: seen.setdefault(payee, set()).add(n in chosen)
  if chosen is None and len({payee for payee in q.payees if payee}) == 1 and (part := share_of(q, said)) is not None:
    return {payee: f"share {part} of {q.amount}" for payee in q.payees if payee}
  return {payee: None for payee in q.payees if payee} | {payee: "yes" if True in flags else "no" for payee, flags in seen.items() if len(flags) == 1}

def with_answer(decisions:dict[str, str], q:Asked, said:str, value:str) -> dict[str, str]:
  rules = for_payees(q, said)
  return {k: v for k, v in (decisions | decided(q, value)).items() if k not in rules} | {k: v for k, v in rules.items() if v is not None}

def questions(held:Case, t:Tables, proposed:dict[str, Decimal]) -> list[Asked]:
  months, ret = months_of(held), []
  groups:dict[str, list[tuple[str, Payment, str]]] = {}
  copied = copies(held, t, months)
  for key, p in held.payments.items():
    if not is_inside(p, months): continue
    if doc := copied.get(key):
      asks = f"the same date, amount and wording are in {doc}, so it is counted once"
      ret.append(Asked(key, worded(p), asks, twice(t, p.way, doc), p.document, "a payment read in two statements", p.amount))
      continue
    if p.way != "in": continue
    if rule_of(held, t, key, p): continue
    if (kind := read_as(held, t, p)) in t.into.asking:
      groups.setdefault(key if key in held.decisions or not payer(p) else alike(p), []).append((key, p, kind))
    elif kind in t.into.feeds and p.check == DIFFERS:
      ret.append(Asked(key, worded(p), ADRIFT, relabelling(t, "in"), p.document, "a payment was left out of the totals", p.amount))
  for subject, members in groups.items(): ret += together(held, t, subject, members)
  for kind, (fact, asking) in t.into.needs.items():
    came = any(p.way == "in" and p.label == kind and is_inside(p, months) and said_of(held, t, key, p) is None for key, p in held.payments.items())
    if (subject := needing(kind)) in held.decisions or (came and not is_given(held, proposed, fact)):
      choices = tuple((instead, f"label it {instead} instead") for instead in picked(t.into) if instead != kind)
      about = f"money labelled {kind} came in and the case gives no {plain(fact)}"
      ret.append(Asked(subject, about, asking, choices, None, t.into.headlines.get(kind), closes=fact))
  rows = counted(held, t, months)
  owed, trading = claims(t, rows), is_trading(held, earned(held, t, rows))
  for doc in dict.fromkeys(q.document for q in owed if q.trade and q.document):
    costs = [q for q in owed if q.trade and q.document == doc]
    if (spent := [q for q in costs if held.payments[q.paid[0]].way == "out"]) and (not trading or trading_in(doc) in held.decisions):
      cnt = sum(len(q.paid) for q in spent)
      ret.append(Asked(trading_in(doc), f"{cnt} payment{'s' if cnt > 1 else ''} in {doc} look{'' if cnt > 1 else 's'} like costs of a business, "
                       "and the case has no business income", "say whether you run a business, even one with no income yet", costing(), doc,
                       "costs of a business with no income yet?"))
    ret += [q for q in costs if is_owed(held, q, trading)]
  return unread(uncovered(held, months)) + ret + [q for q in owed if not q.trade and not is_closed(held, q)] + form_lines(held, t)

def is_closed(held:Case, q:Asked) -> bool: return q.closes is not None and at(held.given, q.closes) not in (None, [])

def payment_asked(held:Case, t:Tables, key:str) -> Asked:
  p = held.payments[key]
  return Asked(key, worded(p), "say what this payment was", relabelling(t, p.way), p.document, amount=p.amount)

def subject_of(held:Case, t:Tables, subject:str) -> Asked:
  if q := next((q for q in questions(held, t, proposals(held, t)[0]) if q.subject == subject), None): return q
  if subject in held.payments: return payment_asked(held, t, subject)
  if q := next((q for q in kept_asks(held, t) if q.subject == subject), None): return q
  if r := held.readings.get(subject):
    misread = ((WRONG, "this figure was misread"),)
    return Asked(subject, f"{r.amount:,} read from {r.quote}", "say whether this figure was misread", misread, r.document)
  raise ValueError(f"the case asks nothing about {subject}")

def numbers(said:str) -> list[int]|None:
  return [int(n) for n in named["nums"].replace(" ", "").split(",")] if (named := NUMBERED.fullmatch(said.strip())) else None

def fitted(held:Case, q:Asked, said:str) -> str:
  said = said.strip()
  if q.share and q.paid and numbers(said) is not None:
    if (named := chosen_in(q, said)) is None:
      raise ValueError(f"answer {q.subject} naming each of payments 1 to {len(q.paid)} at most once, not {said}")
    return f"payments {', '.join(str(n) for n in sorted(named))}"
  if fits(q, said): return said
  numbered = ", payments by number such as payments 1, 3" if q.share and q.paid else ""
  share = f"{numbered}, or the part that was, from 0.01 to {q.amount:,}" if q.share else ""
  raise ValueError(f"answer {q.subject} with one of: {', '.join(n for n, _ in q.choices)}{share}")

def put(given:dict[str, Any], name:str, amt:Decimal|int|bool|list[Decimal]) -> dict[str, Any]:
  part, _, rest = name.partition(".")
  return given | {part: (given.get(part) or {}) | {rest: amt} if rest else amt}

def projected(held:Case, worked:dict[str, tuple[Decimal, str]]) -> dict[str, Any]:
  ret = held.given
  for fact, amt in proposed_from(held, worked)[0].items(): ret = put(ret, fact, amt)
  return ret

def balance(given:dict[str, Any]) -> Figure: return next(fig for fig in assess(from_json(Facts, given)) if fig.rule == "balance of tax")

def scoped(held:Case, doc:str|None, alone:bool=False) -> Case:
  if doc is None: return held
  def own[T:(Payment, Reading, Line)](part:dict[str, T]) -> dict[str, T]: return {k: v for k, v in part.items() if v.document == doc}
  year = yearly(months[0]) if (months := months_of(held)) else held.year
  sigs = set() if alone else {signed(p) for p in own(held.payments).values()}
  payments = {k: p for k, p in held.payments.items() if p.document == doc or signed(p) in sigs}
  return replace(held, year=year, payments=payments, readings=own(held.readings), lines=own(held.lines))

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
  def is_earning(doc:str) -> bool:
    part = scoped(held, doc, alone=True)
    return "business.gross_income" in earned(part, t, counted(part, t, months))
  earning = frozenset(doc for doc in held.documents if is_earning(doc))
  return Base(worked, before, is_trading(held, earned(held, t, counted(held, t, months))), earning)

def priced(held:Case, t:Tables, q:Asked, base:Base) -> dict[str, Figure]:
  ret:dict[str, Figure] = {}
  if base.before is None or q.closes: return ret
  part, elsewhere = scoped(held, q.document), bool(q.document and base.earning - {q.document})
  months, was = months_of(part), amounts(derived(part, t, base.trading))
  for choice in (c for c, _ in q.choices if c not in t.into.needs and c != EACH):
    said = with_answer(held.decisions, q, choice, choice)
    chosen = replace(part, decisions=said)
    rows = counted(chosen, t, months)
    if not any(q.payees) and is_trading(chosen, parts := earned(chosen, t, rows), elsewhere) == base.trading:
      after = amounts(worked_out(chosen, t, rows, parts, base.trading))
      moved = {f: (base.worked.get(f, (ZERO, ""))[0] + after.get(f, ZERO) - was.get(f, ZERO), "") for f in (*base.worked, *after)}
    else: moved = derived(replace(held, decisions=said), t)
    try: now = balance(projected(held, moved))
    except ValueError: continue
    ret[choice] = Figure(choice, now.amt - base.before.amt, now.src)
  return ret if any(fig.amt for fig in ret.values()) else {}
