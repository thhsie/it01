import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from it01.helpers import IT01_LABELLER
from it01.kinds import Prompt
from it01.llm import ask
from it01.rows import Check, Entry
from it01.tax import summed

Moved = tuple[tuple[Entry, Decimal], ...]

@dataclass(frozen=True)
class Labelled:
  date: str
  amt: Decimal
  description: str
  kind: str
  check: Check

def listed(moved:Moved) -> str: return "\n".join(f"{n}. {e.date} {amt:,} {e.description}" for n, (e, amt) in enumerate(moved, 1))

def numbered(moved:Moved) -> list[str]: return [str(n) for n in range(1, len(moved) + 1)]

def answers(moved:Moved, kinds:dict[str, str]) -> dict[str, Any]:
  numbers = numbered(moved)
  return {"type": "object", "properties": {n: {"type": "string", "enum": list(kinds)} for n in numbers},
          "required": numbers, "additionalProperties": False}

def named(moved:Moved, reply:str, kinds:dict[str, str]) -> tuple[Labelled, ...]:
  try: raw = json.loads(reply)
  except json.JSONDecodeError: raise ValueError(f"the model did not answer with JSON {reply}") from None
  if not isinstance(raw, dict): raise ValueError(f"the model must answer with a JSON object, not {type(raw).__name__}")
  if sorted(raw) != sorted(numbered(moved)): raise ValueError(f"the model answered for {sorted(raw)} and there are {len(moved)} lines")
  ret = []
  for n, (e, amt) in enumerate(moved, 1):
    if not isinstance(kind := raw[str(n)], str) or kind not in kinds: raise ValueError(f"unknown kind {kind} for line {n}")
    ret.append(Labelled(e.date, amt, e.description, kind, e.check))
  return tuple(ret)

def totals(found:tuple[Labelled, ...]) -> dict[str, Decimal]: return summed([(c.kind, c.amt) for c in found])

def by_file(moved:Moved, prompt:Prompt) -> tuple[Labelled, ...]:
  try: from it01.local import classified
  except ImportError as e: raise ValueError(f"labelling with a model file needs pip install 'it01[local]' ({e})") from e
  kinds = classified(tuple((amt, e.description) for e, amt in moved), prompt)
  return tuple(Labelled(e.date, amt, e.description, kind, e.check) for (e, amt), kind in zip(moved, kinds, strict=True))

def by_endpoint(moved:Moved, prompt:Prompt, instruction:str) -> tuple[Labelled, ...]:
  said = "\n".join(f"{kind}: {means}" for kind, means in prompt.kinds.items())
  return named(moved, ask(instruction + "\n" + said, listed(moved), answers(moved, prompt.kinds)), prompt.kinds)

def labelled(moved:Moved, prompt:Prompt, instruction:str) -> tuple[Labelled, ...]:
  return by_file(moved, prompt) if IT01_LABELLER else by_endpoint(moved, prompt, instruction)
