import hashlib, json, re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from it01.tax import JSON_TYPES, PLACES, ZERO, Facts, Figure, amount, assess, from_json, is_amount

TITLES = {"documents": "documents you read", "labels": "how money paid in was labelled", "answers": "questions you answered",
          "pending": "questions still open"}
WORDING = ("sources", "texts", "paths", *TITLES)
ASIDE = ("proposed", *WORDING)
PAID_IN = re.compile(r"(?P<amt>\S+) paid in on [^,]*, ")

def once(pairs:list[tuple[str, Any]]) -> dict[str, Any]:
  ret:dict[str, Any] = {}
  for key, value in pairs:
    if key in ret: raise ValueError(f"the same key is written twice {key}")
    ret[key] = value
  return ret

def loaded(text:str) -> Any: return json.loads(text, parse_float=Decimal, object_pairs_hook=once)

def worded(amt:Decimal, date:str, description:str) -> str: return f"{amt:,} paid in on {date}, {description}"

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

def placed(given:dict[str, Any], held:dict[str, dict[str, str]], proposed:dict[str, Decimal], seen:dict[str, tuple[Decimal, str]],
           asking:list[tuple[str, str]]) -> Noted:
  assert set(seen) <= set(PLACES)
  wrote, ask = [], list(asking)
  for name, (amt, quote) in seen.items():
    if (was := at(given, name)) is not None:
      ask.append((f"{name} read as {amt:,} in {quote}, and the file already gives {amount(was):,}",
                  "add it to the fact, or leave the fact if this is the same money read twice"))
    else:
      proposed[name] = proposed.get(name, ZERO) + amt
      held["sources"][name] = f"{said}, {quote}" if (said := held["sources"].get(name)) else quote
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

def confirm(text:str, name:str) -> str:
  given, held, proposed = apart(loaded(text))
  if name not in proposed: raise ValueError(f"nothing is proposed for {name}")
  part, _, field = name.partition(".")
  amt = proposed.pop(name)
  given |= {part: (given.get(part) or {}) | {field: amt} if field else amt}
  return as_file(given, held, proposed)

def answer(text:str, question:str, said:str) -> str:
  given, held, proposed = apart(loaded(text))
  if question not in held["pending"]: raise ValueError(f"no open question {question}")
  if question in held["answers"]: raise ValueError(f"already answered {question}")
  if not said.strip(): raise ValueError(f"the answer to {question} is blank")
  held["answers"][question] = said
  del held["pending"][question]
  return as_file(given, held, proposed)

def labelled(text:str, credit:str) -> list[str]:
  mark = re.compile(re.escape(f", {credit}") + r"( \(\d+\))?$")
  return [k for k in apart(loaded(text))[1]["labels"] if mark.search(k)]

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
  worked = [{"rule": fig.rule, "amount": str(fig.amt),
             "sources": [{"doc": s.doc, "section": s.section, "page": s.page, "url": s.url} for s in fig.src]}
            for fig in assessed(given)]
  return {"facts": texted(given), "proposed": texted(proposed)} | held | {"figures": worked}

def keep(text:str) -> list[str]:
  given, held, proposed = apart(loaded(text))
  worked = figures(given)
  ret = ["facts you confirmed"] + with_wording(given, held["sources"]) + ["", "figures"] + ["  " + line for line in worked]
  if proposed: ret += ["", "figures proposed, not confirmed"] + with_wording(proposed, held["sources"])
  for name, title in TITLES.items():
    if not held[name]: continue
    ret += ["", title]
    for key, value in held[name].items(): ret += [f"  {key}", f"      {value}"]
  return ret
