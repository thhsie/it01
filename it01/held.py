import json, re
from collections.abc import Callable
from dataclasses import dataclass, fields
from decimal import Decimal
from typing import Any
from it01.tax import PLACES, amount

VERSION = {"case": "3"}
RECORDS = ("version", "year", "sources", "confirmed", "documents", "payments", "readings", "lines", "decisions")
AGREES, DIFFERS, UNCHECKED = "ok", "does not agree", "not checked"
WAYS = ("in", "out")
MONTH = re.compile(r"\d{4}-\d{2}")

@dataclass(frozen=True)
class Document:
  kind: str
  path: str
  mark: str
  currency: str|None = None
  ends: str|None = None

@dataclass(frozen=True)
class Payment:
  document: str
  way: str
  amount: Decimal
  date: str
  description: str
  label: str
  check: str
  month: str|None = None

@dataclass(frozen=True)
class Reading:
  document: str
  fact: str
  amount: Decimal
  quote: str

@dataclass(frozen=True)
class Line:
  document: str
  amount: Decimal
  quote: str
  asking: str
  lines: tuple[tuple[str, str], ...]

@dataclass(frozen=True)
class Case:
  given: dict[str, Any]
  year: dict[str, str]
  sources: dict[str, str]
  confirmed: dict[str, str]
  documents: dict[str, Document]
  payments: dict[str, Payment]
  readings: dict[str, Reading]
  lines: dict[str, Line]
  decisions: dict[str, str]

def once(pairs:list[tuple[str, Any]]) -> dict[str, Any]:
  ret:dict[str, Any] = {}
  for key, value in pairs:
    if key in ret: raise ValueError(f"the file has the same key two times {key}")
    ret[key] = value
  return ret

def loaded(text:str) -> Any: return json.loads(text, parse_float=Decimal, object_pairs_hook=once)

def texts(raw:Any, where:str) -> dict[str, str]:
  if not isinstance(raw, dict) or not all(isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip() for k, v in raw.items()):
    raise ValueError(f"{where} must be a JSON object of text, and each text must have words")
  return raw

def part(raw:Any, where:str, need:tuple[str, ...], may:tuple[str, ...]=()) -> dict[str, Any]:
  if not isinstance(raw, dict): raise ValueError(f"{where} must be a JSON object")
  if unknown := sorted(set(raw) - {*need, *may}): raise ValueError(f"{where} has unknown fields {unknown}")
  if missing := [n for n in need if not isinstance(raw.get(n), str) or not raw[n].strip()]: raise ValueError(f"{where} needs {missing} as text")
  if bad := [n for n in may if n in raw and (not isinstance(raw[n], str) or not raw[n].strip())]: raise ValueError(f"{where} needs {bad} as text")
  return raw

def to_document(raw:Any, where:str) -> Document:
  got = part(raw, where, ("kind", "path", "mark"), ("currency", "ends"))
  return Document(got["kind"], got["path"], got["mark"], got.get("currency"), got.get("ends"))

def to_payment(raw:Any, where:str) -> Payment:
  got = part(raw, where, ("document", "way", "amount", "date", "description", "label", "check"), ("month",))
  return Payment(got["document"], got["way"], amount(got["amount"]), got["date"], got["description"], got["label"], got["check"], got.get("month"))

def to_reading(raw:Any, where:str) -> Reading:
  got = part(raw, where, ("document", "fact", "amount", "quote"))
  return Reading(got["document"], got["fact"], amount(got["amount"]), got["quote"])

def to_line(raw:Any, where:str) -> Line:
  if not isinstance(raw, dict): raise ValueError(f"{where} must be a JSON object")
  got = part({k: v for k, v in raw.items() if k != "lines"}, where, ("document", "amount", "quote", "asking"))
  return Line(got["document"], amount(got["amount"]), got["quote"], got["asking"], tuple(texts(raw.get("lines"), f"{where} lines").items()))

def each[T](raw:dict[str, Any], name:str, fxn:Callable[[Any, str], T]) -> dict[str, T]:
  if not isinstance(got := raw.get(name, {}), dict): raise ValueError(f"{name} must be a JSON object")
  return {k: fxn(v, f"{name} {k}") for k, v in got.items()}

def at(given:dict[str, Any], name:str) -> Any:
  part, _, field = name.partition(".")
  if not field: return given.get(part)
  if not isinstance(block := given.get(part, {}), dict): raise ValueError(f"{part} must be a JSON object")
  return block.get(field)

def opened(raw:Any) -> Case:
  if not isinstance(raw, dict): raise ValueError("facts must be a JSON object")
  if ("version" in raw or "documents" in raw) and raw.get("version") != VERSION:
    raise ValueError(f"this engine cannot read a case of version {texts(raw.get('version', {}), 'version').get('case', 'none')}")
  docs, pays = each(raw, "documents", to_document), each(raw, "payments", to_payment)
  reads, lines = each(raw, "readings", to_reading), each(raw, "lines", to_line)
  given = {k: v for k, v in raw.items() if k not in RECORDS}
  year, sources, confirmed = (texts(raw.get(n, {}), n) for n in ("year", "sources", "confirmed"))
  ret = Case(given, year, sources, confirmed, docs, pays, reads, lines, texts(raw.get("decisions", {}), "decisions"))
  owners = [(k, p.document) for k, p in pays.items()] + [(k, r.document) for k, r in reads.items()] + [(k, n.document) for k, n in lines.items()]
  if stray := sorted(k for k, doc in owners if doc not in docs):
    raise ValueError(f"these refer to a document that is not in the case {stray}")
  def is_bad(p:Payment) -> bool:
    return p.way not in WAYS or p.check not in (AGREES, DIFFERS, UNCHECKED) or bool(p.month and not MONTH.fullmatch(p.month))
  if bad := sorted(k for k, p in pays.items() if is_bad(p)):
    raise ValueError(f"these payments have an unknown direction, check or month {bad}")
  if stray := sorted(k for k, r in reads.items() if r.fact not in PLACES): raise ValueError(f"these readings refer to unknown facts {stray}")
  if unknown := sorted(n for n in (*ret.sources, *ret.confirmed) if at(given, n) is None):
    raise ValueError(f"sources and accepted figures refer to facts that are not in the case {unknown}")
  if nested := sorted(k for k in ret.sources if isinstance(given.get(k), dict)): raise ValueError(f"sources cannot refer to {nested}")
  if bad := sorted(k for k, v in ret.confirmed.items() if typed(v) is None): raise ValueError(f"confirmed has a figure that is not an amount {bad}")
  return ret

def typed(said:str) -> Decimal|None:
  try: return amount(said)
  except ValueError: return None

def dumped(value:Any, deep:int=0) -> str:
  pad = "  " * deep
  if value is None: return "null"
  if isinstance(value, bool): return "true" if value else "false"
  if isinstance(value, (int, Decimal)): return str(value)
  if isinstance(value, str): return json.dumps(value)
  if isinstance(value, list) and not value: return "[]"
  if isinstance(value, dict) and not value: return "{}"
  if isinstance(value, list): return "[\n" + ",\n".join(f"{pad}  " + dumped(item, deep + 1) for item in value) + f"\n{pad}]"
  if isinstance(value, dict):
    return "{\n" + ",\n".join(f"{pad}  {json.dumps(k)}: " + dumped(v, deep + 1) for k, v in value.items()) + f"\n{pad}}}"
  raise ValueError(f"a case file cannot have {value}")

def plainly(one:Any) -> dict[str, Any]:
  def plain(v:Any) -> Any: return str(v) if isinstance(v, Decimal) else dict(v) if isinstance(v, tuple) else v
  return {name: plain(v) for name, v in ((f.name, getattr(one, f.name)) for f in fields(one)) if v is not None}

def written(held:Case) -> str:
  kept = {"year": held.year, "sources": held.sources, "confirmed": held.confirmed,
          **{name: {k: plainly(v) for k, v in getattr(held, name).items()} for name in ("documents", "payments", "readings", "lines")},
          "decisions": held.decisions}
  kept = {k: v for k, v in kept.items() if v}
  return dumped(held.given | ({"version": VERSION} if kept.keys() - {"sources"} else {}) | kept) + "\n"
