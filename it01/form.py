import re
from dataclasses import dataclass
from typing import Any
from it01.helpers import data
from it01.rows import month_number
from it01.tax import AMOUNTS

@dataclass(frozen=True)
class Working:
  line: str
  plus: tuple[str, ...]
  less: tuple[str, ...]

@dataclass(frozen=True)
class Form:
  name: str
  fields: tuple[tuple[str, str], ...]
  feeds: tuple[tuple[str, str], ...] = ()
  checks: tuple[Working, ...] = ()
  title: str = ""
  ends: str = ""

def is_titled(form:Form, said:str) -> bool:
  return not form.title or re.search(r"\s+".join(re.escape(word) for word in form.title.split()), said, re.I) is not None

def ending(form:Form, said:str) -> str|None:
  if not (hit := re.search(form.ends, said, re.I)) or not (at := month_number(hit["month"])): return None
  return f"{hit['year']}-{at:02d}"

def text(held:dict[str, Any], key:str, where:str) -> str:
  if not isinstance(got := held.get(key), str) or not got.strip(): raise ValueError(f"{where} must hold {key} as a piece of text")
  return got

def wanted() -> Form:
  held = data("reading").get("form")
  if not isinstance(held, dict): raise ValueError("reading.json must hold a form with a name")
  name = text(held, "name", "reading.json")
  fields = held.get("fields")
  if not isinstance(fields, dict) or not fields or not all(isinstance(v, str) and v.strip() for v in fields.values()):
    raise ValueError("reading.json must hold the form lines as an object of descriptions")
  if marked := sorted(line for line, about in fields.items() if set(about) & set("();")):
    raise ValueError(f"reading.json describes {marked} with a bracket or semicolon, which a question cannot list")
  feeds = held.get("feeds", {})
  if not isinstance(feeds, dict) or not all(isinstance(v, str) for v in feeds.values()):
    raise ValueError("reading.json must hold feeds as an object from a line to a fact")
  if unknown := sorted(set(feeds) - set(fields)): raise ValueError(f"reading.json feeds lines the form does not have {unknown}")
  if unknown := sorted(set(feeds.values()) - set(AMOUNTS)): raise ValueError(f"reading.json feeds facts the package does not know {unknown}")
  if len(set(feeds.values())) != len(feeds): raise ValueError(f"reading.json feeds one fact from more than one line {sorted(feeds)}")
  title, ends = held.get("title", ""), held.get("ends", "")
  if not isinstance(title, str) or not isinstance(ends, str): raise ValueError("reading.json must hold title and ends as text")
  try: groups = set(re.compile(ends).groupindex)
  except re.error as e: raise ValueError(f"reading.json ends is not a pattern {ends}") from e
  if ends and {"month", "year"} - groups: raise ValueError("reading.json ends must name a month and a year")
  return Form(name, tuple(fields.items()), tuple(feeds.items()), checked(held.get("checks", []), set(fields)), title, ends)

def checked(given:Any, lines:set[str]) -> tuple[Working, ...]:
  if not isinstance(given, list): raise ValueError("reading.json must hold checks as a list of sums")
  ret = []
  for one in given:
    if not isinstance(one, dict) or set(one) - {"is", "plus", "less"} or not isinstance(one.get("is"), str):
      raise ValueError("a check in reading.json must say which line it works out, and nothing the package does not read")
    plus, less = (one.get(side, []) for side in ("plus", "less"))
    if not all(isinstance(side, list) and all(isinstance(n, str) for n in side) for side in (plus, less)):
      raise ValueError("a check in reading.json must add and take away lists of line names")
    if not plus and not less: raise ValueError(f"the check on {one['is']} in reading.json adds and takes away nothing")
    if one["is"] in (*plus, *less): raise ValueError(f"the check on {one['is']} in reading.json works it out from itself")
    if not (named := {one["is"], *plus, *less}) <= lines:
      raise ValueError(f"a check in reading.json names lines the form does not have {sorted(named - lines)}")
    ret.append(Working(one["is"], tuple(plus), tuple(less)))
  return tuple(ret)
