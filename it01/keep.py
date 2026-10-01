import hashlib
from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal
from typing import Any
from it01.asks import WRONG, Asked, Base, Tables, based, copies, costs_of, derived, fits, fitted, is_dropped, is_inside, label_of, months_of
from it01.asks import needing, priced, proposals, proposed_from, put, questions, read_as, said_of, subject_of, trading_in, yearly
from it01.held import Case, Document, Line, Payment, Reading, at
from it01.kinds import picked
from it01.law import YEAR_SRC, Source
from it01.tax import LISTS, PLACES, Facts, Figure, amount, assess, from_json, summed

ENTERED = "entered by you"
NIL = Decimal("0.00")
GROUPS = {"income": "counts as income", "exempt": "exempt", "unsorted": "still to sort", "other": "not income"}

def fingerprint(raw:bytes) -> str: return hashlib.sha256(raw).hexdigest()[:32]

def keyed(into:dict[str, Any], doc:str, said:str, one:Any) -> None:
  key, cnt = f"{doc}, {said}", 1
  while key in into: key, cnt = f"{doc}, {said} ({cnt + 1})", cnt + 1
  into[key] = one

def noted(held:Case, name:str, doc:Document, paid:list[tuple[str, Payment]], read:list[Reading], lines:list[tuple[str, Line]]) -> Case:
  if name in held.documents: raise ValueError(f"the case already holds a document {name}")
  payments, readings, asked = dict(held.payments), dict(held.readings), dict(held.lines)
  for said, p in paid: keyed(payments, name, said, p)
  for r in read: keyed(readings, name, r.fact, r)
  for said, one in lines: keyed(asked, name, said, one)
  return replace(held, documents=held.documents | {name: doc}, payments=payments, readings=readings, lines=asked)

def confirm(held:Case, t:Tables, name:str) -> Case:
  proposed, sources = proposals(held, t)
  if name not in proposed: raise ValueError(f"nothing is proposed for {name}")
  return replace(held, given=put(held.given, name, proposed[name]), confirmed=held.confirmed | {name: str(proposed[name])},
                 sources=held.sources | {name: sources[name]})

def cleared(given:dict[str, Any], name:str) -> dict[str, Any]:
  part, _, field = name.partition(".")
  if not field: return {k: v for k, v in given.items() if k != part}
  return given | {part: {k: v for k, v in (given.get(part) or {}).items() if k != field}}

def unconfirmed(held:Case, name:str) -> Case:
  if name not in held.confirmed or held.sources.get(name) == ENTERED: raise ValueError(f"{name} was not confirmed from a proposal")
  return replace(held, given=cleared(held.given, name), confirmed=without(held.confirmed, name), sources=without(held.sources, name))

def without(held:dict[str, str], *names:str) -> dict[str, str]: return {k: v for k, v in held.items() if k not in names}

def yes_or_no(name:str, said:str) -> bool:
  if said not in ("yes", "no"): raise ValueError(f"{name} takes yes or no, not {said}")
  return said == "yes"

def whole(name:str, said:str) -> int:
  if not said.isdecimal(): raise ValueError(f"{name} takes a whole number, not {said}")
  return int(said)

def money_in(name:str, said:str) -> Decimal: return amount(said)

def amounts_in(name:str, said:str) -> list[Decimal]: return [amount(one) for one in said.replace(";", " ").split()]

SETTABLE:dict[str, Callable[[str, str], Any]] = {"resident": yes_or_no, "spouse_above_interest_bar": yes_or_no, "dependants": whole}
SETTABLE |= dict.fromkeys(PLACES, money_in) | dict.fromkeys(LISTS, amounts_in)

def set_fact(held:Case, t:Tables, name:str, said:str) -> Case:
  if (parse := SETTABLE.get(name)) is None: raise ValueError(f"no fact {name} can be entered")
  confirmed, sources = without(held.confirmed, name), without(held.sources, name)
  if said := said.strip().lower():
    given, sources = put(held.given, name, parse(name, said)), sources | {name: ENTERED}
    if name in (worked := derived(held, t)): confirmed |= {name: str(worked[name][0])}
  else: given = cleared(held.given, name)
  from_json(Facts, given)
  return replace(held, given=given, confirmed=confirmed, sources=sources)

def answered(held:Case, t:Tables, subject:str, said:str) -> Case:
  q = subject_of(held, t, subject)
  return replace(held, decisions=held.decisions | {subject: fitted(held, q, said)})

def forgot(held:Case, subject:str) -> Case:
  if subject not in held.decisions: raise ValueError(f"nothing was said about {subject}")
  return replace(held, decisions=without(held.decisions, subject))

def removed(held:Case, t:Tables, name:str) -> Case:
  if name not in held.documents: raise ValueError(f"the case holds no document {name}")
  def kept[T:(Payment, Reading, Line)](part:dict[str, T]) -> dict[str, T]: return {k: v for k, v in part.items() if v.document != name}
  payments = kept(held.payments)
  gone = {*held.payments, *held.readings, *held.lines} - {*payments, *kept(held.readings), *kept(held.lines)}
  gone |= {trading_in(name), *(costs_of(name, kind) for kind in t.out.prompt.kinds), *(costs_of(name, kind, "in") for kind in t.into.business)}
  needs, labels = {needing(kind): kind for kind in t.into.needs}, {p.label for p in payments.values() if p.way == "in"}
  def is_kept(subject:str) -> bool: return subject not in gone and (subject not in needs or needs[subject] in labels)
  return replace(held, documents={k: v for k, v in held.documents.items() if k != name}, payments=payments, readings=kept(held.readings),
                 lines=kept(held.lines), decisions={k: v for k, v in held.decisions.items() if is_kept(k)})

def with_year(held:Case, first:str) -> Case:
  year = yearly(first)
  if clash := sorted(n for n, d in held.documents.items() if d.ends and d.ends != year["to"]):
    raise ValueError(f"{', '.join(clash)} covers another income year, so the case year cannot start in {first}")
  return replace(held, year=year)

def spoke(src:Source) -> str: return f"{src.doc} {src.section} page {src.page}"

def cited(src:Source) -> dict[str, Any]: return {"doc": src.doc, "section": src.section, "page": src.page, "url": src.url}

def assessed(given:dict[str, Any]) -> tuple[Figure, ...]: return assess(from_json(Facts, given))

def figures(given:dict[str, Any]) -> list[str]:
  ret = []
  for fig in assessed(given):
    ret += [f"{fig.rule:<46}{fig.amt:>14,}"] + [f"  {s.section:<42}{s.url}" for s in fig.src]
  return ret

def shown(value:Any) -> str:
  if isinstance(value, bool): return "yes" if value else "no"
  if isinstance(value, str): return value
  return f"{value:,}"

def stated(name:str, value:Any, deep:int) -> list[str]:
  pad = "  " * deep
  if isinstance(value, list):
    return [f"{pad}{name}"] + [line for n, item in enumerate(value, 1) for line in stated(str(n), item, deep + 1)]
  if isinstance(value, dict): return [f"{pad}{name}"] + states(value, deep + 1)
  return [f"{pad}{name:<{max(14, 46 - len(pad))}}{shown(value):>14}"]

def states(given:dict[str, Any], deep:int) -> list[str]: return [line for name, value in given.items() for line in stated(name, value, deep)]

def with_wording(given:dict[str, Any], sources:dict[str, str], deep:int=1, prefix:str="") -> list[str]:
  ret = []
  for name, value in given.items():
    if isinstance(value, dict): ret += [f"{'  ' * deep}{name}"] + with_wording(value, sources, deep + 1, f"{prefix}{name}.")
    else: ret += stated(name, value, deep)
    if said := sources.get(f"{prefix}{name}"): ret.append(f"{'  ' * (deep + 2)}{said}")
  return ret

def texted(value:Any) -> Any:
  if isinstance(value, (bool, str)): return value
  if isinstance(value, (int, Decimal)): return str(value)
  if isinstance(value, list): return [texted(one) for one in value]
  if isinstance(value, dict): return {name: texted(one) for name, one in value.items()}
  raise ValueError(f"a case holds no {type(value).__name__} {value}")

def received(held:Case, t:Tables) -> dict[str, Any]:
  table = t.into
  earning = tuple(kind for kind in (*table.feeds, *table.needs) if kind not in table.exempt)
  where = {kind: group for group, kinds in (("income", earning), ("exempt", table.exempt), ("unsorted", table.asking),
                                             ("other", (*table.not_income, *table.business))) for kind in kinds}
  months = months_of(held)
  copied = copies(held, t, months)
  paid = [(key, p, where.get(label_of(held, t, key, p), "unsorted"), label_of(held, t, key, p)) for key, p in held.payments.items()
          if p.way == "in" and not is_dropped(said_of(held, t, key, p), key, copied)]
  inside = [one for one in paid if is_inside(one[1], months)]
  def by_month(m:str) -> list[tuple[str, Payment, str, str]]: return [one for one in inside if one[1].month == m]
  return {"groups": {g: summed([(group, p.amount) for _, p, group, _ in inside]).get(g, NIL) for g in GROUPS},
          "kinds": dict(sorted(summed([(kind, p.amount) for _, p, _, kind in inside]).items(), key=lambda one: -one[1])), "group_of": where,
          "months": {m: {"total": sum((p.amount for _, p, _, _ in by_month(m)), NIL), "groups": summed([(g, p.amount) for _, p, g, _ in by_month(m)]),
                         "payments": {g: [k for k, _, gg, _ in by_month(m) if gg == g] for g in dict.fromkeys(g for _, _, g, _ in by_month(m))}}
                     for m in months},
          "outside": [k for k, p, _, _ in paid if not is_inside(p, months)], "undated": [k for k, p, _, _ in paid if p.month is None]}

def said_to(held:Case, q:Asked) -> str|None: return said if (said := held.decisions.get(q.subject)) is not None and fits(q, said) else None

def asked_data(held:Case, t:Tables, q:Asked, base:Base) -> dict[str, Any]:
  said = said_to(held, q)
  prices = {} if said is not None else priced(held, t, q, base)
  shown = {c: {"amount": str(f.amt), "sources": [cited(s) for s in f.src]} for c, f in prices.items()}
  return {"subject": q.subject, "about": q.about, "asks": q.asks, "choices": [list(c) for c in q.choices], "document": q.document,
          "headline": q.headline, "amount": str(q.amount), "payments": list(q.paid), "share": q.share, "said": said, "closes": q.closes,
          "earlier": held.decisions.get(q.subject) if said is None else None, "prices": shown}

def case(held:Case, t:Tables) -> dict[str, Any]:
  base, months = based(held, t), months_of(held)
  proposed, proposing = proposed_from(held, base.worked)
  asked = questions(held, t, proposed)
  money = texted(received(held, t)) | {"year_sources": [cited(s) for s in YEAR_SRC]}
  payments = {key: {"document": p.document, "way": p.way, "amount": str(p.amount), "date": p.date, "description": p.description,
                    "label": label_of(held, t, key, p), "read": read_as(held, t, p), "check": p.check, "month": p.month,
                    "said": held.decisions.get(key)} for key, p in held.payments.items()}
  readings = {key: {"document": r.document, "fact": r.fact, "amount": str(r.amount), "quote": r.quote, "wrong": held.decisions.get(key) == WRONG}
              for key, r in held.readings.items()}
  changed = {fact: {"was": texted(at(held.given, fact)), "source": proposing[fact]} for fact in proposed if at(held.given, fact) is not None}
  sources = held.sources | {n: said for n, said in proposing.items() if at(held.given, n) is None}
  return {"facts": texted(held.given), "proposed": texted(proposed), "changed": changed, "sources": sources, "confirmed": held.confirmed,
          "year": held.year, "documents": {n: d.kind for n, d in held.documents.items()},
          "outside": [k for k, p in held.payments.items() if not is_inside(p, months)],
          "questions": [asked_data(held, t, q, base) for q in asked], "payments": payments, "readings": readings,
          "kinds": {"in": list(picked(t.into)), "out": list(t.out.prompt.kinds)},
          "figures": [{"rule": f.rule, "amount": str(f.amt), "sources": [cited(s) for s in f.src]} for f in assessed(held.given)], "received": money}

def keep(held:Case, t:Tables) -> list[str]:
  base = based(held, t)
  proposed, proposing = proposed_from(held, base.worked)
  ret = ["facts you confirmed"] + with_wording(held.given, held.sources) + ["", "figures"] + ["  " + line for line in figures(held.given)]
  if proposed: ret += ["", "figures proposed, not confirmed"] + with_wording(proposed, proposing)
  money = received(held, t)
  if money["kinds"]:
    freed = [f"    {spoke(s)}" for s in t.into.exempt.values()]
    ret += ["", "money paid in, by what it counts as, as labelled"]
    ret += [line for group, amt in money["groups"].items() for line in [f"  {GROUPS[group]:<44}{amt:>14,}"] + (freed if group == "exempt" else [])]
    ret += ["", "money paid in, by the kind it was labelled"]
    ret += [f"  {kind:<27}{GROUPS[money['group_of'].get(kind, 'unsorted')]:<17}{amt:>14,}" for kind, amt in money["kinds"].items()]
  if year := list(money["months"]):
    ret += ["", f"money paid in over the income year from {year[0]} to {year[-1]}, {', '.join(spoke(s) for s in YEAR_SRC)}"]
    ret += [f"  {m:<44}{one['total']:>14,}" for m, one in money["months"].items()]
  if money["outside"]: ret += ["", "money paid in outside that income year"] + [f"  {key}" for key in money["outside"]]
  if money["undated"]: ret += ["", "money paid in with a date whose month is not clear"] + [f"  {key}" for key in money["undated"]]
  if held.documents: ret += ["", "documents you read"] + [f"  {n:<44}{d.kind}" for n, d in held.documents.items()]
  if held.payments:
    ret += ["", "how each payment was labelled"]
    for key, p in held.payments.items():
      said = held.decisions.get(key)
      ret += [f"  {key}", f"      {label_of(held, t, key, p)}" + (", as you said" if said else f", {p.check}" if p.check != "ok" else "")]
  if held.readings:
    ret += ["", "what each form was read as"]
    for key, r in held.readings.items():
      ret += [f"  {key}", f"      {r.amount:,} read from {r.quote}" + (", misread as you said" if held.decisions.get(key) == WRONG else "")]
  asked = questions(held, t, proposed)
  if waiting := [q for q in asked if said_to(held, q) is None]:
    ret += ["", "questions still open"]
    for q in waiting:
      ret += [f"  {q.subject}"] + ([f"      {q.headline}"] if q.headline else []) + ([f"      {q.about}"] if q.about != q.subject else [])
      ret += [f"      {q.asks}: " + "; ".join(f"{n} ({d})" for n, d in q.choices)]
      if q.share: ret += [f"      {n}. {p.date} {p.amount:,} {p.description}" for n, p in enumerate((held.payments[k] for k in q.paid), 1)]
      for choice, fig in priced(held, t, q, base).items(): ret += [f"      {choice:<30}{fig.amt:>+14,}"]
  if done := [(q, said) for q in asked if (said := said_to(held, q)) is not None]:
    ret += ["", "questions you answered"] + [line for q, said in done for line in (f"  {q.subject}", f"      {said}")]
  return ret
