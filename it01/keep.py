import hashlib, json, re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from it01.form import wanted
from it01.kinds import ADRIFT, Paying, Table, paying, picked, spoken
from it01.law import YEAR_SRC, YEAR_STARTS, Source
from it01.rows import months
from it01.tax import JSON_TYPES, PLACES, ZERO, Facts, Figure, amount, assess, from_json, is_amount, plain, summed

TITLES = {"documents": "documents you read", "labels": "how money paid in was labelled", "answers": "questions you answered",
          "pending": "questions still open"}
WORDING = ("sources", "texts", "paths", *TITLES)
ASIDE = ("proposed", *WORDING)
NIL = Decimal("0.00")
GROUPS = {"income": "counts as income", "exempt": "exempt", "unsorted": "still to sort", "other": "not income"}
PAID_IN = re.compile(r"(?P<amt>\S+) paid in on (?P<date>[^,]*), ")
TWICE = re.compile(r"(?P<name>.+) read as (?P<amt>\S+) in (?P<quote>.+), and the case already gives (?P<was>\S+)")
BOTH = ("add", "leave")
ON_LINE = re.compile(r"(?P<amt>\S+) on the line (?P<quote>.+)")
LACKING = re.compile(r"money labelled (?P<kind>\S+) came in and the case gives no (?P<fact>.+)")
PAID_OUT = re.compile(r"(?P<amt>\S+) paid out in \d+ payments? that looks? like (?P<kind>[^,]+), in (?P<doc>.+)")
LINES = re.compile(r"([^\s;(]+) \([^)]*\)")

def once(pairs:list[tuple[str, Any]]) -> dict[str, Any]:
  ret:dict[str, Any] = {}
  for key, value in pairs:
    if key in ret: raise ValueError(f"the same key is written twice {key}")
    ret[key] = value
  return ret

def loaded(text:str) -> Any: return json.loads(text, parse_float=Decimal, object_pairs_hook=once)

def worded(amt:Decimal, date:str, description:str) -> str: return f"{amt:,} paid in on {date}, {description}"
def spent_on(question:str) -> tuple[str, Decimal]|None:
  return (spent["kind"].replace(" ", "_"), amount(spent["amt"])) if (spent := PAID_OUT.fullmatch(question)) else None

def fact_for(table:Paying, kind:str) -> str|None: return claim[0] if (claim := (table.claims | table.business).get(kind)) else None

def choices_for(table:Paying, kind:str, amt:Decimal) -> tuple[tuple[str, str], ...]:
  if fact := fact_for(table, kind): return (("yes", f"adds {amt:,} to {plain(fact)}"), ("no", "adds nothing"))
  return (("later", "you will add the certificate"), ("not", f"it is not {plain(kind)}"))

def asking_for(table:Paying, kind:str, amt:Decimal) -> str:
  said = claim[1] if (claim := (table.claims | table.business).get(kind)) else table.certificates[kind]
  return offering(said, choices_for(table, kind, amt))

def lacking(kind:str, fact:str) -> str: return f"money labelled {kind} came in and the case gives no {plain(fact)}"
def needing(table:Table, kind:str) -> str:
  return offering(table.needs[kind][1], (("later", "you will add it"), ("not", f"the money is not {plain(kind)}")))
def adrift() -> str: return offering(ADRIFT, (("noted", "it stays left out"),))

def answers_to(question:str, asks:str) -> str:
  out, table = paying(), spoken("labelling")
  if (spent := spent_on(question)) and spent[0] in out.prompt.kinds and spent[0] not in out.aside: return asking_for(out, *spent)
  if (need := LACKING.fullmatch(question)) and need["kind"] in table.needs: return needing(table, need["kind"])
  return adrift() if asks == ADRIFT else asks

def closed(question:str, asks:str) -> list[str]:
  shown = answers_to(question, asks)
  return lines_of(shown) if LACKING.fullmatch(question) or shown == adrift() else []

def typed(said:str) -> Decimal|None:
  try: return amount(said)
  except ValueError: return None

def taken(question:str, said:str) -> tuple[str, Decimal]|None:
  if not (spent := spent_on(question)): return None
  table, (kind, amt), said = paying(), spent, said.strip()
  if kind not in table.prompt.kinds: raise ValueError(f"{question} names no kind of payment out")
  choices, fact = [name for name, _ in choices_for(table, kind, amt)], fact_for(table, kind)
  if said in choices: return (fact, amt) if fact and said == "yes" else None
  part = typed(said) if kind in table.business else None
  if fact and part is not None and ZERO < part <= amt: return fact, part
  share = f", or the part that was, from 0.01 to {amt:,}" if kind in table.business else ""
  raise ValueError(f"answer {question} with one of: {', '.join(choices)}{share}")

def outgoing(amt:Decimal, cnt:int, kind:str, doc:str) -> str:
  return f"{amt:,} paid out in {cnt} payment{'s' if cnt > 1 else ''} that look{'' if cnt > 1 else 's'} like {plain(kind)}, in {doc}"

def fingerprint(raw:bytes) -> str: return hashlib.sha256(raw).hexdigest()[:32]

def wording(raw:dict[str, Any], name:str) -> dict[str, str]:
  if name not in raw: return {}
  held = raw[name]
  if not isinstance(held, dict) or not all(isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip() for k, v in held.items()):
    raise ValueError(f"{name} must be a JSON object of text, with nothing left blank")
  return held

def at(given:dict[str, Any], name:str) -> Any:
  part, _, field = name.partition(".")
  if not field: return given.get(part)
  if not isinstance(block := given.get(part, {}), dict): raise ValueError(f"{part} must be a JSON object")
  return block.get(field)

def is_given(given:dict[str, Any], proposed:dict[str, Decimal], name:str) -> bool: return at(given, name) is not None or name in proposed

def offered(raw:dict[str, Any]) -> dict[str, Decimal]:
  if not isinstance(held := raw.get("proposed", {}), dict): raise ValueError("proposed must be a JSON object of figures")
  if unknown := sorted(set(held) - set(PLACES)): raise ValueError(f"proposed names figures that are not facts {unknown}")
  ret = {}
  for name, value in held.items():
    if type(value) not in JSON_TYPES[Decimal] or not is_amount(Decimal(value)): raise ValueError(f"invalid proposed {name} {value}")
    ret[name] = Decimal(value)
  return ret

def apart(raw:Any) -> tuple[dict[str, Any], dict[str, dict[str, str]], dict[str, Decimal]]:
  if not isinstance(raw, dict): raise ValueError("facts must be a JSON object")
  held, proposed = {name: wording(raw, name) for name in WORDING}, offered(raw)
  given = {k: v for k, v in raw.items() if k not in ASIDE}
  if both := sorted(n for n in proposed if at(given, n) is not None): raise ValueError(f"proposed repeats facts already given {both}")
  if unknown := sorted(n for n in held["sources"] if not is_given(given, proposed, n)):
    raise ValueError(f"sources name neither a fact nor a proposed figure {unknown}")
  if nested := sorted(k for k in held["sources"] if isinstance(given.get(k), (dict, list))): raise ValueError(f"sources cannot name {nested}")
  return given, held, proposed

def dumped(value:Any, deep:int=0) -> str:
  pad = "  " * deep
  if isinstance(value, bool): return "true" if value else "false"
  if isinstance(value, (int, Decimal)): return str(value)
  if isinstance(value, str): return json.dumps(value)
  if isinstance(value, list) and not value: return "[]"
  if isinstance(value, dict) and not value: return "{}"
  if isinstance(value, list): return "[\n" + ",\n".join(f"{pad}  " + dumped(item, deep + 1) for item in value) + f"\n{pad}]"
  if isinstance(value, dict):
    return "{\n" + ",\n".join(f"{pad}  {json.dumps(k)}: " + dumped(v, deep + 1) for k, v in value.items()) + f"\n{pad}}}"
  raise ValueError(f"a case file cannot hold {value}")

@dataclass(frozen=True)
class Document:
  name: str
  path: str
  mark: str
  kind: str

@dataclass(frozen=True)
class Noted:
  proposed: tuple[str, ...]
  asked: tuple[str, ...]
  answered: tuple[str, ...]

def as_file(given:dict[str, Any], held:dict[str, dict[str, str]], proposed:dict[str, Decimal]) -> str:
  whole:dict[str, Any] = given | ({"proposed": proposed} if proposed else {})
  return dumped(whole | {k: v for k, v in held.items() if v}) + "\n"

def quoted(sources:dict[str, str], name:str, quote:str) -> str: return f"{said}, {quote}" if (said := sources.get(name)) else quote

def placed(given:dict[str, Any], held:dict[str, dict[str, str]], proposed:dict[str, Decimal], seen:dict[str, tuple[Decimal, str]],
           asking:list[tuple[str, str]]) -> Noted:
  assert set(seen) <= set(PLACES)
  wrote, ask = [], list(asking)
  for name, (amt, quote) in seen.items():
    if (was := at(given, name)) is not None:
      ask.append((f"{plain(name)} read as {amt:,} in {quote}, and the case already gives {amount(was):,}",
                  ("add it if this is more money, or leave it if the same money was read twice: "
                   f"add (it becomes {amount(was) + amt:,}); leave (it stays {amount(was):,})")))
    else:
      proposed[name] = proposed.get(name, ZERO) + amt
      held["sources"][name] = quoted(held["sources"], name, quote)
      wrote.append(name)
  before = tuple(q for q, _ in ask if q in held["answers"])
  fresh = [(q, asks) for q, asks in ask if q not in before]
  for question, asks in fresh:
    if held["pending"].get(question, asks) != asks: raise ValueError(f"the same question is already open with different wording {question}")
    held["pending"][question] = asks
  return Noted(tuple(wrote), tuple(q for q, _ in fresh), before)

def noted(text:str, seen:dict[str, tuple[Decimal, str]], doc:Document, asking:list[tuple[str, str]],
          labels:tuple[tuple[str, str], ...]=()) -> tuple[str, Noted]:
  given, held, proposed = apart(loaded(text))
  how = placed(given, held, proposed, seen, asking)
  repeats:dict[str, int] = {}
  for said, kind in labels:
    repeats[said] = cnt = repeats.get(said, 0) + 1
    held["labels"][f"{doc.name}, {said}" + (f" ({cnt})" if cnt > 1 else "")] = kind
  held["documents"][doc.name] = doc.kind
  held["texts"][doc.mark] = doc.name
  held["paths"][doc.name] = doc.path
  return as_file(given, held, proposed), how

def put(given:dict[str, Any], name:str, amt:Decimal) -> dict[str, Any]:
  part, _, field = name.partition(".")
  return given | {part: (given.get(part) or {}) | {field: amt} if field else amt}

def confirm(text:str, name:str) -> str:
  given, held, proposed = apart(loaded(text))
  if name not in proposed: raise ValueError(f"nothing is proposed for {name}")
  return as_file(put(given, name, proposed.pop(name)), held, proposed)

def answer(text:str, question:str, said:str) -> str:
  given, held, proposed = apart(loaded(text))
  if question not in held["pending"]: raise ValueError(f"no open question {question}")
  if question in held["answers"]: raise ValueError(f"already answered {question}")
  if not said.strip(): raise ValueError(f"the answer to {question} is blank")
  held["answers"][question] = said
  del held["pending"][question]
  return as_file(given, held, proposed)

def reanswered(text:str, question:str, said:str, fact:str|None, amt:Decimal) -> str:
  given, held, proposed = apart(loaded(text))
  if fact:
    if at(given, fact) is not None: raise ValueError(f"{fact} is confirmed, so {question} cannot be changed")
    if proposed.get(fact, ZERO) < amt: raise ValueError(f"{fact} no longer holds the {amt:,} that {question} added")
    rest, cnt = re.subn(rf"(^|, ){re.escape(f'answered {question}')}(?=, |$)", "", held["sources"].get(fact, ""))
    if cnt != 1: raise ValueError(f"the source of {fact} does not name {question} once, so its amount cannot be taken back")
    left, rest = proposed[fact] - amt, rest.removeprefix(", ")
    if rest: held["sources"][fact] = rest
    else: held["sources"].pop(fact, None)
    if left or rest: proposed[fact] = left
    else: del proposed[fact]
  held["answers"][question] = said
  return as_file(given, held, proposed)

def increased(text:str, question:str) -> str:
  given, held, proposed = apart(loaded(text))
  if not (asked := TWICE.fullmatch(question)) or not (name := next((n for n in PLACES if plain(n) == asked["name"]), "")):
    raise ValueError(f"{question} does not add to a figure")
  if (was := at(given, name)) is None or amount(was) != amount(asked["was"]):
    raise ValueError(f"{asked['name']} is no longer {asked['was']}, so it cannot be added to")
  held["sources"][name] = quoted(held["sources"], name, asked["quote"])
  return as_file(put(given, name, amount(was) + amount(asked["amt"])), held, proposed)

def labelled(text:str, credit:str) -> list[str]:
  mark = re.compile(re.escape(f", {credit}") + r"( \(\d+\))?$")
  return [k for k in apart(loaded(text))[1]["labels"] if mark.search(k)]

def offering(asking:str, lines:tuple[tuple[str, str], ...]) -> str: return f"{asking}: " + "; ".join(f"{n} ({d})" for n, d in lines)
def lines_of(asks:str) -> list[str]: return LINES.findall(asks.partition(": ")[2])

def proposing(text:str, seen:dict[str, tuple[Decimal, str]]) -> tuple[str, Noted]:
  given, held, proposed = apart(loaded(text))
  how = placed(given, held, proposed, seen, [])
  return as_file(given, held, proposed), how

def relabelled(text:str, keys:list[str], kind:str, seen:dict[str, tuple[Decimal, str]]) -> tuple[str, Noted]:
  given, held, proposed = apart(loaded(text))
  for key in keys: held["labels"][key] = kind
  how = placed(given, held, proposed, seen, [])
  return as_file(given, held, proposed), how

def shown(value:Any) -> str:
  if isinstance(value, bool): return "yes" if value else "no"
  if isinstance(value, str): return value
  return f"{value:,}"

def assessed(given:dict[str, Any]) -> tuple[Figure, ...]: return assess(from_json(Facts, given))

def balance(given:dict[str, Any]) -> Figure: return next(fig for fig in assessed(given) if fig.rule == "balance of tax")

def priced(text:str) -> dict[str, dict[str, Figure]]:
  given, held, _ = apart(loaded(text))
  table, out, before, ret = spoken("labelling"), paying(), balance(given), {}
  def worth(choice:str, name:str|None, amt:Decimal) -> Figure:
    after = balance(put(given, name, (ZERO if (was := at(given, name)) is None else amount(was)) + amt)) if name else before
    return Figure(choice, after.amt - before.amt, after.src)
  for question, asks in held["pending"].items():
    if (twice := TWICE.fullmatch(question)) and (added := next((n for n in PLACES if plain(n) == twice["name"]), None)):
      if (was := at(given, added)) is None or amount(was) != amount(twice["was"]): continue
      ret[question] = {"add": worth("add", added, amount(twice["amt"])), "leave": worth("leave", None, ZERO)}
    elif (paid := PAID_IN.match(question)) and asks in table.asking.values():
      ret[question] = {kind: worth(kind, table.feeds.get(kind), amount(paid["amt"])) for kind in picked(table) if kind not in table.needs}
    elif (spent := spent_on(question)) and (fact := fact_for(out, spent[0])):
      ret[question] = {"yes": worth("yes", fact, spent[1]), "no": worth("no", None, ZERO)}
    elif (read := ON_LINE.fullmatch(question)) and (lines := lines_of(asks)):
      feeds = dict(wanted().feeds)
      ret[question] = {line: worth(line, feeds.get(line), amount(read["amt"])) for line in lines}
  return ret

def figures(given:dict[str, Any]) -> list[str]:
  ret = []
  for fig in assessed(given):
    ret += [f"{fig.rule:<46}{fig.amt:>14,}"] + [f"  {s.section:<42}{s.url}" for s in fig.src]
  return ret

def stated(name:str, value:Any, deep:int) -> list[str]:
  pad = "  " * deep
  if isinstance(value, list):
    return [f"{pad}{name}"] + [line for n, item in enumerate(value, 1) for line in [f"{pad}  {n}"] + states(item, deep + 2)]
  if isinstance(value, dict): return [f"{pad}{name}"] + states(value, deep + 1)
  return [f"{pad}{name:<{max(14, 46 - len(pad))}}{shown(value):>14}"]

def states(given:dict[str, Any], deep:int) -> list[str]:
  return [line for name, value in given.items() for line in stated(name, value, deep)]

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

def case(text:str) -> dict[str, Any]:
  given, held, proposed = apart(loaded(text))
  worked = [{"rule": fig.rule, "amount": str(fig.amt), "sources": [cited(s) for s in fig.src]} for fig in assessed(given)]
  money = texted(received(held, spoken("labelling"))) | {"year_sources": [cited(s) for s in YEAR_SRC]}
  priced_out = {question: {choice: {"amount": str(fig.amt), "sources": [cited(s) for s in fig.src]} for choice, fig in each.items()}
                for question, each in priced(text).items()}
  pending = {question: answers_to(question, asks) for question, asks in held["pending"].items()}
  worked_out = {"pending": pending, "figures": worked, "received": money, "prices": priced_out}
  return {"facts": texted(given), "proposed": texted(proposed)} | held | worked_out

@dataclass(frozen=True)
class Paid:
  key: str
  doc: str
  amt: Decimal
  date: str
  kind: str

def credited(key:str, kind:str, docs:list[str], table:Table) -> Paid|None:
  doc = next((d for d in docs if key.startswith(f"{d}, ")), None)
  if doc is None or kind not in table.prompt.kinds or not (m := PAID_IN.match(key[len(doc) + 2:])): return None
  try: return Paid(key, doc, amount(m["amt"]), m["date"], kind)
  except ValueError: return None

def year_of(month:str) -> tuple[str, ...]:
  first = int(month[:4]) - (int(month[5:]) < YEAR_STARTS)
  return tuple(f"{first + (YEAR_STARTS - 1 + n) // 12}-{(YEAR_STARTS - 1 + n) % 12 + 1:02d}" for n in range(12))

def spoke(src:Source) -> str: return f"{src.doc} {src.section} page {src.page}"

def cited(src:Source) -> dict[str, Any]: return {"doc": src.doc, "section": src.section, "page": src.page, "url": src.url}

def received(held:dict[str, dict[str, str]], table:Table) -> dict[str, Any]:
  where = {kind: group for group, kinds in (("income", (*table.feeds, *table.needs)), ("exempt", table.exempt), ("unsorted", table.asking),
                                             ("other", table.not_income)) for kind in kinds}
  docs = sorted(held["documents"], key=len, reverse=True)
  read = {key: credited(key, kind, docs, table) for key, kind in held["labels"].items()}
  found = [p for p in read.values() if p is not None]
  ways = {doc: months(tuple(p.date for p in found if p.doc == doc)) for doc in {p.doc for p in found}}
  dated = [(p, ways[p.doc][p.date]) for p in found]
  kinds = summed([(p.kind, p.amt) for p in found])
  groups = summed([(where[p.kind], p.amt) for p in found])
  year = year_of(last) if (last := max((at for _, at in dated if at), default="")) else ()
  by_month = {m: [p for p, at in dated if at == m] for m in year}
  return {"groups": {group: groups.get(group, NIL) for group in GROUPS}, "kinds": dict(sorted(kinds.items(), key=lambda one: -one[1])),
          "group_of": where,
          "months": {m: {"total": sum((p.amt for p in paid), NIL), "groups": summed([(where[p.kind], p.amt) for p in paid]),
                         "payments": {g: [p.key for p in paid if where[p.kind] == g] for g in dict.fromkeys(where[p.kind] for p in paid)}}
                     for m, paid in by_month.items()},
          "outside": [p.key for p, at in dated if at and at not in year],
          "undated": [p.key for p, at in dated if at is None], "unread": [key for key, p in read.items() if p is None]}

def keep(text:str) -> list[str]:
  given, held, proposed = apart(loaded(text))
  worked = figures(given)
  ret = ["facts you confirmed"] + with_wording(given, held["sources"]) + ["", "figures"] + ["  " + line for line in worked]
  if proposed: ret += ["", "figures proposed, not confirmed"] + with_wording(proposed, held["sources"])
  table = spoken("labelling")
  money = received(held, table)
  if money["kinds"]:
    freed = [f"    {spoke(s)}" for s in table.exempt.values()]
    ret += ["", "money paid in, by what it counts as, as labelled"]
    ret += [line for group, amt in money["groups"].items() for line in [f"  {GROUPS[group]:<44}{amt:>14,}"] + (freed if group == "exempt" else [])]
    ret += ["", "money paid in, by the kind it was labelled"]
    ret += [f"  {kind:<27}{GROUPS[money['group_of'][kind]]:<17}{amt:>14,}" for kind, amt in money["kinds"].items()]
  if year := list(money["months"]):
    ret += ["", f"money paid in over the income year from {year[0]} to {year[-1]}, {', '.join(spoke(s) for s in YEAR_SRC)}"]
    ret += [f"  {m:<44}{one['total']:>14,}" for m, one in money["months"].items()]
  if money["outside"]: ret += ["", "money paid in outside that income year"] + [f"  {key}" for key in money["outside"]]
  if money["undated"]: ret += ["", "money paid in with a date whose month is not clear"] + [f"  {key}" for key in money["undated"]]
  if money["unread"]: ret += ["", "labels that do not read as money paid in"] + [f"  {key}" for key in money["unread"]]
  for name, title in TITLES.items():
    if not held[name]: continue
    ret += ["", title]
    for key, value in held[name].items(): ret += [f"  {key}", f"      {value}"]
  if worths := priced(text):
    ret += ["", "what each answer changes in the tax to pay"]
    for question, each in worths.items():
      ret.append(f"  {question}")
      for choice, fig in each.items(): ret += [f"    {choice:<30}{fig.amt:>+14,}"] + [f"      {s.section:<40}{s.url}" for s in fig.src]
  return ret
