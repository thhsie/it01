import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from it01.helpers import IT01_LABELLER, instruction
from it01.kinds import Table, spoken
from it01.llm import ask
from it01.rows import Check, Entry, entries
from it01.tax import summed

ADRIFT = "the balance after this does not agree, so it is left out"

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

def received(text:str) -> tuple[Entry, ...]: return tuple(e for e in entries(text) if e.paid_in is not None)

def listed(paid:tuple[Entry, ...]) -> str:
  return "\n".join(f"{n}. {e.date} {e.paid_in:,} {e.description}" for n, e in enumerate(paid, 1))

def numbered(paid:tuple[Entry, ...]) -> list[str]: return [str(n) for n in range(1, len(paid) + 1)]

def answers(paid:tuple[Entry, ...], kinds:dict[str, str]) -> dict[str, Any]:
  numbers = numbered(paid)
  return {"type": "object", "properties": {n: {"type": "string", "enum": list(kinds)} for n in numbers},
          "required": numbers, "additionalProperties": False}

def named(paid:tuple[Entry, ...], reply:str, kinds:dict[str, str]) -> tuple[Credit, ...]:
  try: raw = json.loads(reply)
  except json.JSONDecodeError: raise ValueError(f"the model did not answer with JSON {reply}") from None
  if not isinstance(raw, dict): raise ValueError(f"the model must answer with a JSON object, not {type(raw).__name__}")
  if sorted(raw) != sorted(numbered(paid)):
    raise ValueError(f"the model answered for {sorted(raw)} and there are {len(paid)} credits")
  ret = []
  for n, e in enumerate(paid, 1):
    if not isinstance(kind := raw[str(n)], str) or kind not in kinds: raise ValueError(f"unknown kind {kind} for credit {n}")
    assert e.paid_in is not None
    ret.append(Credit(e.date, e.paid_in, e.description, kind, e.check))
  return tuple(ret)

def asked(found:tuple[Credit, ...], asking:dict[str, str]) -> tuple[Question, ...]:
  return tuple(Question(c.date, c.amt, c.description, asking[c.kind]) for c in found if c.kind in asking)

def fed(found:tuple[Credit, ...], feeds:dict[str, str]) -> tuple[dict[str, tuple[Decimal, str]], tuple[Question, ...]]:
  ret:dict[str, tuple[Decimal, str]] = {}
  for kind, fact in feeds.items():
    if not (same := [c for c in found if c.kind == kind and c.check is not Check.DIFFERS]): continue
    unsure = sum(1 for c in same if c.check is Check.UNCHECKED)
    ret[fact] = (sum((c.amt for c in same), Decimal(0)), f"{len(same)} labelled {kind}" + (f", {unsure} unchecked" if unsure else ""))
  adrift = tuple(Question(c.date, c.amt, c.description, ADRIFT) for c in found if c.kind in feeds and c.check is Check.DIFFERS)
  return ret, adrift

def totals(found:tuple[Credit, ...]) -> dict[str, Decimal]: return summed([(c.kind, c.amt) for c in found])

def by_file(paid:tuple[Entry, ...], table:Table) -> tuple[Credit, ...]:
  try: from it01.local import classified
  except ImportError as e: raise ValueError(f"labelling with a model file needs pip install 'it01[local]' ({e})") from e
  pairs = [(e, e.paid_in) for e in paid if e.paid_in is not None]
  kinds = classified(tuple((amt, e.description) for e, amt in pairs), table.kinds, table.examples)
  return tuple(Credit(e.date, amt, e.description, kind, e.check) for (e, amt), kind in zip(pairs, kinds, strict=True))

def by_endpoint(paid:tuple[Entry, ...], table:Table) -> tuple[Credit, ...]:
  said = "\n".join(f"{kind}: {means}" for kind, means in table.kinds.items())
  return named(paid, ask(instruction("labelling") + "\n" + said, listed(paid), answers(paid, table.kinds)), table.kinds)

def label(text:str) -> tuple[tuple[Credit, ...], tuple[Question, ...]]:
  table = spoken("labelling")
  if not (paid := received(text)): return (), ()
  found = by_file(paid, table) if IT01_LABELLER else by_endpoint(paid, table)
  return found, asked(found, table.asking)
