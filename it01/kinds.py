from dataclasses import dataclass
from it01.helpers import data
from it01.law import DOCS, Source
from it01.tax import PLACES

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

def picked(table:Table) -> tuple[str, ...]: return tuple(kind for kind in table.kinds if kind not in table.asking)
