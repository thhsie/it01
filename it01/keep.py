import json
from decimal import Decimal
from typing import Any
from it01.tax import Facts, assess, from_json

ASIDE = ("sources", "answers")

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

def apart(raw:Any) -> tuple[dict[str, Any], dict[str, str], dict[str, str]]:
  if not isinstance(raw, dict): raise ValueError("facts must be a JSON object")
  sources, answers = wording(raw, "sources"), wording(raw, "answers")
  given = {k: v for k, v in raw.items() if k not in ASIDE}
  if unknown := sorted(set(sources) - set(given)): raise ValueError(f"sources name facts that were not given {unknown}")
  if nested := sorted(k for k in sources if isinstance(given[k], (dict, list))): raise ValueError(f"sources cannot name {nested}")
  return given, sources, answers

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

def confirmed(given:dict[str, Any], sources:dict[str, str]) -> list[str]:
  ret = []
  for name, value in given.items():
    ret += stated(name, value, 1)
    if said := sources.get(name): ret.append(f"      {said}")
  return ret

def keep(text:str) -> list[str]:
  given, sources, answers = apart(loaded(text))
  worked = figures(given)
  ret = ["facts you confirmed"] + confirmed(given, sources) + ["", "figures"] + ["  " + line for line in worked]
  if answers:
    ret += ["", "questions you answered"]
    for asked, said in answers.items(): ret += [f"  {asked}", f"      {said}"]
  return ret
