import json
from decimal import Decimal
from typing import Any
from it01.tax import AMOUNTS, JSON_TYPES, Facts, assess, from_json, is_amount

TITLES = {"documents": "documents you read", "answers": "questions you answered", "pending": "questions still open"}
WORDING = ("sources", *TITLES)
ASIDE = ("proposed", *WORDING)

def once(pairs:list[tuple[str, Any]]) -> dict[str, Any]:
  ret:dict[str, Any] = {}
  for key, value in pairs:
    if key in ret: raise ValueError(f"the same key is written twice {key}")
    ret[key] = value
  return ret

def loaded(text:str) -> Any: return json.loads(text, parse_float=Decimal, object_pairs_hook=once)

def wording(raw:dict[str, Any], name:str) -> dict[str, str]:
  if name not in raw: return {}
  held = raw[name]
  if not isinstance(held, dict) or not all(isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip() for k, v in held.items()):
    raise ValueError(f"{name} must be a JSON object of text, with nothing left blank")
  return held

def offered(raw:dict[str, Any]) -> dict[str, Decimal]:
  if not isinstance(held := raw.get("proposed", {}), dict): raise ValueError("proposed must be a JSON object of figures")
  if unknown := sorted(set(held) - set(AMOUNTS)): raise ValueError(f"proposed names figures that are not facts {unknown}")
  ret = {}
  for name, value in held.items():
    if type(value) not in JSON_TYPES[Decimal] or not is_amount(Decimal(value)): raise ValueError(f"invalid proposed {name} {value}")
    ret[name] = Decimal(value)
  return ret

def apart(raw:Any) -> tuple[dict[str, Any], dict[str, dict[str, str]], dict[str, Decimal]]:
  if not isinstance(raw, dict): raise ValueError("facts must be a JSON object")
  held, proposed = {name: wording(raw, name) for name in WORDING}, offered(raw)
  given = {k: v for k, v in raw.items() if k not in ASIDE}
  if both := sorted(set(proposed) & set(given)): raise ValueError(f"proposed repeats facts already given {both}")
  if unknown := sorted(set(held["sources"]) - set(given) - set(proposed)):
    raise ValueError(f"sources name neither a fact nor a proposed figure {unknown}")
  if nested := sorted(k for k in held["sources"] if isinstance(given.get(k), (dict, list))): raise ValueError(f"sources cannot name {nested}")
  return given, held, proposed

def shown(value:Any) -> str:
  if isinstance(value, bool): return "yes" if value else "no"
  if isinstance(value, str): return value
  return f"{value:,}"

def figures(given:dict[str, Any]) -> list[str]:
  ret = []
  for fig in assess(from_json(Facts, given)):
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

def with_wording(given:dict[str, Any], sources:dict[str, str]) -> list[str]:
  ret = []
  for name, value in given.items():
    ret += stated(name, value, 1)
    if said := sources.get(name): ret.append(f"      {said}")
  return ret

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
