import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from it01.helpers import IT01_LABELLER, data, instruction
from it01.law import DOCS, Source
from it01.llm import ask
from it01.rows import Check, Entry, entries
from it01.tax import PLACES

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

@dataclass(frozen=True)
class Table:
  name: str
  kinds: dict[str, str]
  feeds: dict[str, str]
  asking: dict[str, str]
  needs: dict[str, tuple[str, str]]
  exempt: dict[str, Source]
  examples: tuple[tuple[str, str], ...]

def spoken(name:str) -> Table:
  held = data(name)
  if not isinstance(called := held.get("name"), str) or not called.strip(): raise ValueError(f"{name}.json must say what it reads")
  ret = []
  for field in ("kinds", "asking"):
    part = held.get(field)
    if not isinstance(part, dict) or not part or not all(isinstance(v, str) for v in part.values()):
      raise ValueError(f"{name}.json must hold {field} as an object of names")
    ret.append({str(k): v for k, v in part.items()})
  kinds, asking = ret
  if not isinstance(given := held.get("feeds", {}), dict) or not all(isinstance(v, str) for v in given.values()):
    raise ValueError(f"{name}.json must hold feeds as an object of names")
  feeds = {str(k): v for k, v in given.items()}
  for part, what in ((feeds, "feeds from"), (asking, "asks about")):
    if unknown := sorted(set(part) - set(kinds)): raise ValueError(f"{name}.json {what} unknown kinds {unknown}")
  if unknown := sorted(set(feeds.values()) - set(PLACES)): raise ValueError(f"{name}.json feeds unknown facts {unknown}")
  if both := sorted(set(feeds) & set(asking)): raise ValueError(f"{name}.json both feeds and asks about {both}")
  fills = list(feeds.values())
  if twice := sorted({f for f in fills if fills.count(f) > 1}): raise ValueError(f"{name}.json feeds {twice} from more than one kind")
  if not isinstance(wanted := held.get("needs", {}), dict): raise ValueError(f"{name}.json must hold needs as an object")
  needs = {}
  for kind, need in wanted.items():
    if not isinstance(need, dict) or not all(isinstance(need.get(k), str) and need[k].strip() for k in ("fact", "asking")):
      raise ValueError(f"{name}.json must give a fact and a question for what {kind} needs")
    needs[str(kind)] = (need["fact"], need["asking"])
  if unknown := sorted(set(needs) - set(kinds)): raise ValueError(f"{name}.json needs unknown kinds {unknown}")
  if unknown := sorted({f for f, _ in needs.values()} - set(PLACES)): raise ValueError(f"{name}.json needs unknown facts {unknown}")
  if both := sorted({f for f, _ in needs.values()} & set(fills)): raise ValueError(f"{name}.json both feeds and needs {both}")
  if not isinstance(freed := held.get("exempt", {}), dict): raise ValueError(f"{name}.json must hold exempt as an object")
  exempt = {}
  for kind, src in freed.items():
    said = src.get("section") if isinstance(src, dict) else None
    if not isinstance(src, dict) or src.get("doc") not in DOCS or not isinstance(said, str) or not said.strip() or type(src.get("page")) is not int:
      raise ValueError(f"{name}.json must give the document, section and page that exempt {kind}")
    exempt[str(kind)] = Source(src["doc"], src["section"], src["page"])
  if unknown := sorted(set(exempt) - set(kinds)): raise ValueError(f"{name}.json exempts unknown kinds {unknown}")
  if both := sorted(set(exempt) & (set(feeds) | set(needs) | set(asking))): raise ValueError(f"{name}.json both exempts and uses {both}")
  shown = held.get("examples", [])
  if not isinstance(shown, list): raise ValueError(f"{name}.json must hold examples as a list")
  if bad := next((e for e in shown if not (isinstance(e, list) and len(e) == 2 and all(isinstance(x, str) and x.strip() for x in e))), None):
    raise ValueError(f"{name}.json gives an example {bad!r} that is not a credit and its kind")
  if unknown := sorted({k for _, k in shown} - set(kinds)): raise ValueError(f"{name}.json gives examples of unknown kinds {unknown}")
  return Table(called, kinds, feeds, asking, needs, exempt, tuple((t, k) for t, k in shown))

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

def picked(table:Table) -> tuple[str, ...]: return tuple(kind for kind in table.kinds if kind not in table.asking)

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

def totals(found:tuple[Credit, ...]) -> dict[str, Decimal]:
  ret:dict[str, Decimal] = {}
  for c in found: ret[c.kind] = ret.get(c.kind, Decimal(0)) + c.amt
  return ret

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
