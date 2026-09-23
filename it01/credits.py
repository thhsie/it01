import json
from dataclasses import dataclass
from decimal import Decimal
from it01.helpers import data, instruction
from it01.llm import ask
from it01.rows import Check, Entry, entries

@dataclass(frozen=True)
class Credit:
  date: str
  amt: Decimal
  description: str
  kind: str
  check: Check

@dataclass(frozen=True)
class Question:
  date: str
  amt: Decimal
  description: str
  asking: str

def spoken(name:str) -> tuple[str, dict[str, str], dict[str, str]]:
  held = data(name)
  if not isinstance(called := held.get("name"), str) or not called.strip(): raise ValueError(f"{name}.json must say what it reads")
  ret = []
  for field in ("kinds", "asking"):
    part = held.get(field)
    if not isinstance(part, dict) or not part or not all(isinstance(v, str) for v in part.values()):
      raise ValueError(f"{name}.json must hold {field} as an object of names")
    ret.append({str(k): v for k, v in part.items()})
  if unknown := sorted(set(ret[1]) - set(ret[0])): raise ValueError(f"{name}.json asks about unknown kinds {unknown}")
  return called, ret[0], ret[1]

def received(text:str) -> tuple[Entry, ...]: return tuple(e for e in entries(text) if e.paid_in is not None)

def listed(paid:tuple[Entry, ...]) -> str:
  return "\n".join(f"{n}. {e.date} {e.paid_in:,} {e.description}" for n, e in enumerate(paid, 1))

def named(paid:tuple[Entry, ...], reply:str, kinds:dict[str, str]) -> tuple[Credit, ...]:
  try: raw = json.loads(reply)
  except json.JSONDecodeError: raise ValueError(f"the model did not answer with JSON {reply}") from None
  if not isinstance(raw, dict): raise ValueError(f"the model must answer with a JSON object, not {type(raw).__name__}")
  if sorted(raw) != sorted(str(n) for n in range(1, len(paid) + 1)):
    raise ValueError(f"the model answered for {sorted(raw)} and there are {len(paid)} credits")
  ret = []
  for n, e in enumerate(paid, 1):
    if not isinstance(kind := raw[str(n)], str) or kind not in kinds: raise ValueError(f"unknown kind {kind} for credit {n}")
    assert e.paid_in is not None
    ret.append(Credit(e.date, e.paid_in, e.description, kind, e.check))
  return tuple(ret)

def asked(found:tuple[Credit, ...], asking:dict[str, str]) -> tuple[Question, ...]:
  return tuple(Question(c.date, c.amt, c.description, asking[c.kind]) for c in found if c.kind in asking)

def totals(found:tuple[Credit, ...]) -> dict[str, Decimal]:
  ret:dict[str, Decimal] = {}
  for c in found: ret[c.kind] = ret.get(c.kind, Decimal(0)) + c.amt
  return ret

def label(text:str) -> tuple[tuple[Credit, ...], tuple[Question, ...]]:
  _, kinds, asking = spoken("labelling")
  if not (paid := received(text)): return (), ()
  said = "\n".join(f"{kind}: {means}" for kind, means in kinds.items())
  return (found := named(paid, ask(instruction("labelling") + "\n" + said, listed(paid)), kinds)), asked(found, asking)
