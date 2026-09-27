from dataclasses import fields
from typing import Any
from it01.helpers import data
from it01.law import Addition, Period
from it01.tax import Facts, Figure, assess, is_held

ADDITIONS = {Addition.RETIRED: "R", Addition.DISABLED: "D"}
CATEGORIES = "ABCDE"
MOST_DEPENDANTS = 4

def part_of(f:Facts, name:str) -> Any:
  held:Any = f
  for step in name.split("."): held = getattr(held, step)
  return held

def valued(f:Facts, figs:dict[str, Figure], kind:str, name:str) -> Any:
  match kind:
    case "fact": return part_of(f, name)
    case "figure": return figs[name].amt if name in figs else None
    case "emoluments": return f.emoluments
    case "dependant":
      idx, _, field = name.partition(".")
      return getattr(f.dependant_income[int(idx)], field) if int(idx) < len(f.dependant_income) else None
    case "count": return min(part_of(f, name), MOST_DEPENDANTS) or None
    case "yesno": return "Yes" if part_of(f, name) else "No"
    case "category": return CATEGORIES[min(f.dependants, len(CATEGORIES) - 1)] if f.resident else None
    case "addition": return ADDITIONS.get(part_of(f, name))
    case _: raise AssertionError(f"portal.json holds an unknown kind of field {kind}")

def sheet(f:Facts) -> list[tuple[str, str]]:
  if f.period is not Period.YEAR: raise ValueError(f"the return takes a year, not a {f.period.name.lower()}")
  table, figs = data("portal"), {fig.rule: fig for fig in assess(f)}
  checks, ret = set(table["checks"]), []
  for field, spec in table["fields"]:
    kind, _, name = spec.partition(":")
    if kind == "each":
      ret += [(field.replace("{n}", str(idx)), str(v)) for idx, v in enumerate(part_of(f, name), 1) if v]
    elif (value := valued(f, figs, kind, name)) is not None and (value or field in checks):
      ret.append((field, str(value)))
  return ret

def untyped(f:Facts) -> list[str]:
  notes, defaults = data("portal")["untyped"], {one.name: one.default for one in fields(Facts)}
  return [f"{name} {note}" for name, note in notes.items() if is_held(getattr(f, name), defaults[name])]
