from dataclasses import dataclass
from decimal import Decimal
from it01.helpers import instruction
from it01.kinds import spoken
from it01.labels import Labelled, Moved, labelled
from it01.rows import Check, entries

ADRIFT = "the balance after this does not agree, so it is left out"

@dataclass(frozen=True)
class Question:
  date: str
  amt: Decimal
  description: str
  asking: str

def received(text:str) -> Moved: return tuple((e, e.paid_in) for e in entries(text) if e.paid_in is not None)

def asked(found:tuple[Labelled, ...], asking:dict[str, str]) -> tuple[Question, ...]:
  return tuple(Question(c.date, c.amt, c.description, asking[c.kind]) for c in found if c.kind in asking)

def fed(found:tuple[Labelled, ...], feeds:dict[str, str]) -> tuple[dict[str, tuple[Decimal, str]], tuple[Question, ...]]:
  ret:dict[str, tuple[Decimal, str]] = {}
  for kind, fact in feeds.items():
    if not (same := [c for c in found if c.kind == kind and c.check is not Check.DIFFERS]): continue
    unsure = sum(1 for c in same if c.check is Check.UNCHECKED)
    ret[fact] = (sum((c.amt for c in same), Decimal(0)), f"{len(same)} labelled {kind}" + (f", {unsure} unchecked" if unsure else ""))
  adrift = tuple(Question(c.date, c.amt, c.description, ADRIFT) for c in found if c.kind in feeds and c.check is Check.DIFFERS)
  return ret, adrift

def label(text:str) -> tuple[tuple[Labelled, ...], tuple[Question, ...]]:
  table = spoken("labelling")
  if not (paid := received(text)): return (), ()
  found = labelled(paid, table.prompt, instruction("labelling"))
  return found, asked(found, table.asking)
