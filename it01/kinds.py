from dataclasses import dataclass
from typing import Any
from it01.helpers import data
from it01.law import DOCS, Source
from it01.tax import LISTS, PLACES

@dataclass(frozen=True)
class Prompt:
  name: str
  kinds: dict[str, str]
  examples: tuple[tuple[str, str], ...]
  task: str
  instruction: str
  line: str

def prompted(name:str, held:dict[str, Any]) -> Prompt:
  if not isinstance(called := held.get("name"), str) or not called.strip(): raise ValueError(f"{name}.json must say what it reads")
  kinds = held.get("kinds")
  if not isinstance(kinds, dict) or not kinds or not all(isinstance(v, str) for v in kinds.values()):
    raise ValueError(f"{name}.json must hold kinds as an object of names")
  shown = held.get("examples", [])
  if not isinstance(shown, list): raise ValueError(f"{name}.json must hold examples as a list")
  if bad := next((e for e in shown if not (isinstance(e, list) and len(e) == 2 and all(isinstance(x, str) and x.strip() for x in e))), None):
    raise ValueError(f"{name}.json gives an example {bad!r} that is not a line and its kind")
  if unknown := sorted({k for _, k in shown} - set(kinds)): raise ValueError(f"{name}.json gives examples of unknown kinds {unknown}")
  if not isinstance(said := held.get("model"), dict): raise ValueError(f"{name}.json must hold model as an object")
  if missing := [k for k in ("task", "instruction", "line") if not isinstance(said.get(k), str) or not said[k].strip()]:
    raise ValueError(f"{name}.json gives the model no {missing}")
  if missing := [n for n in ("amount", "description") if "{" + n + "}" not in said["line"]]:
    raise ValueError(f"the line wording in {name}.json leaves out {missing}")
  return Prompt(called, {str(k): v for k, v in kinds.items()}, tuple((t, k) for t, k in shown), said["task"], said["instruction"], said["line"])

@dataclass(frozen=True)
class Table:
  prompt: Prompt
  feeds: dict[str, str]
  asking: dict[str, str]
  needs: dict[str, tuple[str, str]]
  exempt: dict[str, Source]
  not_income: tuple[str, ...]
  headlines: dict[str, str]

def spoken(name:str) -> Table:
  held = data(name)
  prompt = prompted(name, held)
  kinds = prompt.kinds
  part = held.get("asking")
  if not isinstance(part, dict) or not part or not all(isinstance(v, str) for v in part.values()):
    raise ValueError(f"{name}.json must hold asking as an object of names")
  asking = {str(k): v for k, v in part.items()}
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
  needs, headlines = {}, {}
  for kind, need in wanted.items():
    if not isinstance(need, dict) or not all(isinstance(need.get(k), str) and need[k].strip() for k in ("fact", "asking", "headline")):
      raise ValueError(f"{name}.json must give a fact, a question and a headline for what {kind} needs")
    needs[str(kind)] = (need["fact"], need["asking"])
    headlines[str(kind)] = need["headline"]
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
  if both := sorted(set(exempt) & (set(needs) | set(asking))): raise ValueError(f"{name}.json both exempts and uses {both}")
  aside = held.get("not_income", [])
  if not isinstance(aside, list) or not all(isinstance(k, str) for k in aside):
    raise ValueError(f"{name}.json must hold not_income as a list of kinds")
  if unknown := sorted(set(aside) - set(kinds)): raise ValueError(f"{name}.json calls unknown kinds not income {unknown}")
  if both := sorted(set(aside) & (set(feeds) | set(needs) | set(asking) | set(exempt))):
    raise ValueError(f"{name}.json both uses and sets aside {both}")
  if loose := sorted(set(kinds) - set(feeds) - set(needs) - set(asking) - set(exempt) - set(aside)):
    raise ValueError(f"{name}.json says nothing of how {loose} count")
  return Table(prompt, feeds, asking, needs, exempt, tuple(aside), headlines)

def picked(table:Table) -> tuple[str, ...]: return tuple(kind for kind in table.prompt.kinds if kind not in table.asking)

@dataclass(frozen=True)
class Paying:
  prompt: Prompt
  claims: dict[str, tuple[str, str]]
  certificates: dict[str, tuple[str, str|None]]
  business: dict[str, tuple[str, str]]
  aside: tuple[str, ...]
  headlines: dict[str, str]

def questions(name:str, held:dict[str, Any], part:str) -> dict[str, str]:
  if not isinstance(got := held.get(part, {}), dict) or not all(isinstance(v, str) and v.strip() for v in got.values()):
    raise ValueError(f"{name}.json must hold {part} as an object of questions")
  return {str(k): v for k, v in got.items()}

def facts(name:str, held:dict[str, Any], part:str) -> dict[str, tuple[str, str]]:
  if not isinstance(given := held.get(part, {}), dict): raise ValueError(f"{name}.json must hold {part} as an object")
  ret = {}
  for kind, claim in given.items():
    if not isinstance(claim, dict) or not all(isinstance(claim.get(k), str) and claim[k].strip() for k in ("fact", "asking")):
      raise ValueError(f"{name}.json must give a fact and a question for {kind}")
    ret[str(kind)] = (claim["fact"], claim["asking"])
  if unknown := sorted({fact for fact, _ in ret.values()} - set(PLACES)): raise ValueError(f"{name}.json {part} unknown facts {unknown}")
  return ret

def figured(held:dict[str, Any]) -> dict[str, tuple[str, str|None]]:
  if not isinstance(given := held.get("certificates", {}), dict): raise ValueError("paying.json must hold certificates as an object")
  ret = {}
  for kind, said in given.items():
    if not isinstance(said, dict) or not isinstance(said.get("asking"), str) or not said["asking"].strip() or set(said) - {"asking", "fact"}:
      raise ValueError(f"paying.json must give a question, and at most a fact, for the certificate of {kind}")
    if (fact := said.get("fact")) is not None and fact not in (*PLACES, *LISTS):
      raise ValueError(f"paying.json certificates name an unknown fact {fact}")
    ret[str(kind)] = (said["asking"], fact)
  return ret

def paying() -> Paying:
  held = data("paying")
  prompt = prompted("paying", held)
  claims, business, certificates = facts("paying", held, "claims"), facts("paying", held, "business"), figured(held)
  if not isinstance(aside := held.get("aside", []), list) or not all(isinstance(k, str) for k in aside):
    raise ValueError("paying.json must hold aside as a list of kinds")
  headlines = questions("paying", held, "headlines")
  uses = (set(claims), set(certificates), set(business), set(aside))
  if unknown := sorted(set().union(*uses) - set(prompt.kinds)): raise ValueError(f"paying.json uses unknown kinds {unknown}")
  if twice := sorted(k for k in prompt.kinds if sum(k in use for use in uses) > 1): raise ValueError(f"paying.json gives {twice} more than one use")
  if loose := sorted(set(prompt.kinds) - set().union(*uses)): raise ValueError(f"paying.json says nothing of how {loose} count")
  if stray := sorted(set(headlines) - set(prompt.kinds)): raise ValueError(f"paying.json gives headlines for unknown kinds {stray}")
  return Paying(prompt, claims, certificates, business, tuple(aside), headlines)
