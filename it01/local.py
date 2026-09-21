import itertools, math, pathlib, re
import numpy as np, onnxruntime, tokenizers
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from it01.helpers import IT01_MODEL_FILE, IT01_TOKENISER, data
from it01.read import AMOUNTS, amount

WORD = re.compile(r"\w+|[^\w\s]")
SURE = 50
QUARTER = 4
LIMIT = 700
TRIES = 4096
Span = tuple[int, Decimal]
Way = dict[Span, str]
Spans = tuple[tuple[Span, tuple[str, ...]], ...]
ROLES = ("tokens", "attention", "words", "word_mask", "lines", "line_mask")
ANSWERS = (("spans", 4), ("scores", 3), ("valid", 3))
TAKEN = {"form": ("name", "described", "listed"), "describes": ("line", "means"), "lists": ("line",), "document": ("text",)}
PARTS = tuple(TAKEN)

@dataclass(frozen=True)
class Schema:
  form: str
  describes: str
  lists: str
  document: str

@dataclass(frozen=True)
class Shape:
  takes: tuple[str, ...]
  gives: tuple[str, ...]
  schema: Schema
  line_mark: str
  text_mark: str
  word_start: str

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

@dataclass(frozen=True)
class Found:
  field: str
  amt: Decimal
  quote: str
  sure: int
  at: int

@dataclass(frozen=True)
class Told:
  fact: str
  amt: Decimal
  quote: str
  line: str

@dataclass(frozen=True)
class Asked:
  amt: Decimal
  quote: str
  asking: str
  lines: tuple[tuple[str, str], ...]

@dataclass(frozen=True)
class Sum:
  line: str
  says: Decimal
  adds: Decimal
  can_grow: bool
  can_shrink: bool
  @property
  def agrees(self) -> bool: return self.says == self.adds
  @property
  def wrong(self) -> bool: return (self.adds > self.says and not self.can_shrink) or (self.adds < self.says and not self.can_grow)

def words(text:str) -> tuple[tuple[str, int, int], ...]:
  return tuple((m.group().lower(), m.start(), m.end()) for m in WORD.finditer(text))

def written(shape:Shape, form:Form, said:tuple[tuple[str, int, int], ...]) -> str:
  s = shape.schema
  described = "".join(s.describes.format(line=name, means=means) for name, means in form.fields)
  listed = "".join(s.lists.format(line=name) for name, _ in form.fields)
  return s.form.format(name=form.name, described=described, listed=listed) + s.document.format(text=" ".join(w for w, _, _ in said))

def marker(tok:Any, name:str) -> int:
  if (at := tok.token_to_id(name)) is None: raise ValueError(f"the tokeniser has no {name}, so it does not go with this model")
  return int(at)

def prompt(tok:Any, said:tuple[tuple[str, int, int], ...], form:Form, shape:Shape) -> tuple[list[int], list[int], list[int]]:
  coded = tok.encode(written(shape, form, said), add_special_tokens=False)
  sep, mark = marker(tok, shape.text_mark), marker(tok, shape.line_mark)
  if sep not in coded.ids: raise ValueError("the tokeniser did not mark where the document starts")
  starts = [i for i in range(coded.ids.index(sep) + 1, len(coded.ids)) if coded.tokens[i].startswith(shape.word_start)]
  if len(starts) != len(said) + 1:
    raise ValueError(f"the tokeniser split {len(said)} words into {max(len(starts) - 1, 0)}, so the wording cannot be traced")
  markers = [i for i, x in enumerate(coded.ids) if x == mark]
  if len(markers) != len(form.fields): raise ValueError(f"the tokeniser marked {len(markers)} of {len(form.fields)} lines")
  return coded.ids, starts[:len(said)], markers

def room(tok:Any, said:tuple[tuple[str, int, int], ...], form:Form, shape:Shape, cap:int) -> int:
  low, high = 0, len(said)
  while low < high:
    mid = (low + high + 1) // 2
    if len(tok.encode(written(shape, form, said[:mid]), add_special_tokens=False).ids) <= cap: low = mid
    else: high = mid - 1
  if not low: raise ValueError(f"the form leaves no room for the document in a model file that takes {cap} tokens")
  return low

def windows(tok:Any, said:tuple[tuple[str, int, int], ...], form:Form, shape:Shape, size:dict[str, int]) -> list[tuple[int, int]]:
  ret, at = [], 0
  while at < len(said):
    cnt = room(tok, said[at:at + size["words"]], form, shape, size["tokens"])
    ret.append((at, cnt))
    if at + cnt >= len(said): return ret
    at += max(cnt - max(cnt // QUARTER, 1), 1)
  return ret

def sizes(session:Any, shape:Shape) -> dict[str, int]:
  held = {}
  for d in session.get_inputs():
    if len(d.shape) < 2: raise ValueError(f"the model file takes {d.name} in {len(d.shape)} dimensions and this gives 2")
    if not isinstance(size := d.shape[1], int): raise ValueError(f"the model file leaves {d.name} unsized, and this reads a model of fixed size")
    held[d.name] = size
  if set(held) != set(shape.takes): raise ValueError(f"the model file wants {sorted(held)} and model.json names {list(shape.takes)}")
  return {role: held[name] for role, name in zip(ROLES, shape.takes)}

def filled(values:list[int], size:int, name:str) -> tuple[np.ndarray, np.ndarray]:
  if len(values) > size: raise ValueError(f"this needs room for {len(values)} {name} and the model file takes {size}")
  spare = size - len(values)
  return np.array([values + [0] * spare], dtype=np.int64), np.array([[True] * len(values) + [False] * spare])

def feed(size:dict[str, int], shape:Shape, ids:list[int], starts:list[int], markers:list[int]) -> dict[str, np.ndarray]:
  tokens, attention = filled(ids, size["tokens"], "tokens")
  spots, kept = filled(starts, size["words"], "words")
  queries, asked = filled(markers, size["lines"], "lines")
  return dict(zip(shape.takes, (tokens, attention.astype(np.int64), spots, kept, queries, asked)))

def answer(session:Any, fed:dict[str, np.ndarray], shape:Shape) -> dict[str, np.ndarray]:
  names = [d.name for d in session.get_outputs()]
  if missing := sorted(set(shape.gives) - set(names)): raise ValueError(f"the model file answers with {names} and model.json names {missing}")
  held = dict(zip(names, session.run(None, fed)))
  ret = {}
  for name, (role, dims) in zip(shape.gives, ANSWERS):
    if held[name].ndim != dims: raise ValueError(f"the model file gives {name} in {held[name].ndim} dimensions and this reads {dims}")
    ret[role] = held[name]
  return ret

def score(logit:Any) -> int: return round(100 / (1 + math.exp(-max(min(logit, LIMIT), -LIMIT))))

def spans(session:Any, tok:Any, said:tuple[tuple[str, int, int], ...], form:Form, shape:Shape,
          size:dict[str, int]) -> dict[str, list[tuple[int, int, int]]]:
  ids, starts, markers = prompt(tok, said, form, shape)
  out = answer(session, feed(size, shape, ids, starts, markers), shape)
  ret:dict[str, list[tuple[int, int, int]]] = {name: [] for name, _ in form.fields}
  for q, (name, _) in enumerate(form.fields):
    for c in range(out["spans"].shape[2]):
      if not out["valid"][0][q][c]: continue
      sure = score(out["scores"][0][q][c])
      first, last = int(out["spans"][0][q][c][0]), int(out["spans"][0][q][c][1])
      if sure < SURE or first >= last or last > len(said): continue
      ret[name].append((sure, first, last))
  return ret

def batched(form:Form, size:int) -> list[Form]:
  return [Form(form.name, form.fields[at:at + size]) for at in range(0, len(form.fields), size)]

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
  feeds = held.get("feeds", {})
  if not isinstance(feeds, dict) or not all(isinstance(v, str) for v in feeds.values()):
    raise ValueError("reading.json must hold feeds as an object from a line to a fact")
  if unknown := sorted(set(feeds) - set(fields)): raise ValueError(f"reading.json feeds lines the form does not have {unknown}")
  if unknown := sorted(set(feeds.values()) - set(AMOUNTS)): raise ValueError(f"reading.json feeds facts the package does not know {unknown}")
  if len(set(feeds.values())) != len(feeds): raise ValueError(f"reading.json feeds one fact from more than one line {sorted(feeds)}")
  return Form(name, tuple(fields.items()), tuple(feeds.items()), checked(held.get("checks", []), set(fields)))

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

def sums(form:Form, amts:dict[str, Decimal]) -> tuple[Sum, ...]:
  ret = []
  for check in form.checks:
    if check.line not in amts or not {*check.plus, *check.less} & set(amts): continue
    adds = sum((amts.get(n, Decimal(0)) for n in check.plus), Decimal(0)) - sum((amts.get(n, Decimal(0)) for n in check.less), Decimal(0))
    ret.append(Sum(check.line, amts[check.line], adds, any(n not in amts for n in check.plus), any(n not in amts for n in check.less)))
  return tuple(ret)

def claimed(seen:tuple[Found, ...]) -> Spans:
  by:dict[Span, list[str]] = {}
  for f in sorted(seen, key=lambda f: -f.sure): by.setdefault((f.at, f.amt), []).append(f.field)
  return tuple((where, tuple(dict.fromkeys(lines))) for where, lines in sorted(by.items()))

def amounts(way:Way) -> dict[str, Decimal]|None:
  ret:dict[str, Decimal] = {}
  for (_, amt), line in way.items():
    if ret.setdefault(line, amt) != amt: return None
  return ret

def ways(form:Form, held:Spans) -> list[Way]:
  loose = [(where, lines) for where, lines in held if len(lines) > 1]
  if math.prod(len(lines) + 1 for _, lines in loose) > TRIES: return []
  fixed = {where: lines[0] for where, lines in held if len(lines) == 1}
  ret = []
  for pick in itertools.product(*[(*lines, "") for _, lines in loose]):
    way = fixed | {where: line for line, (where, _) in zip(pick, loose) if line}
    if (amts := amounts(way)) is not None and not any(one.wrong for one in sums(form, amts)): ret.append(way)
  return ret

def narrowed(held:Spans, kept:list[Way]) -> dict[Span, tuple[str, ...]]:
  ret = {}
  for where, lines in held:
    took = [way.get(where, "") for way in kept] if kept else list(lines)
    ret[where] = tuple(dict.fromkeys(n for n in took if n))
  return ret

def fitted(form:Form, kept:list[Way], settled:Way) -> dict[str, Decimal]:
  ret, mark = amounts(settled) or {}, (-1, -1)
  for way in kept:
    amts = amounts(way) or {}
    if (score := (sum(1 for one in sums(form, amts) if one.agrees), len(way))) > mark: ret, mark = amts, score
  return ret

def tells(form:Form, seen:tuple[Found, ...]) -> tuple[tuple[Told, ...], tuple[Asked, ...], tuple[Sum, ...]]:
  held = claimed(seen)
  kept = ways(form, held)
  left = narrowed(held, kept)
  desc = dict(form.fields)
  quotes:dict[Span, str] = {}
  for f in sorted(seen, key=lambda f: -f.sure): quotes.setdefault((f.at, f.amt), f.quote)
  ret, ask = [], {}
  for line, fact in form.feeds:
    mine = [where for where, lines in left.items() if line in lines]
    if not mine: continue
    if all(len(left[where]) == 1 for where in mine) and len({amt for _, amt in mine}) == 1:
      at, amt = mine[0]
      ret.append(Told(fact, amt, quotes[(at, amt)], line))
    else:
      for where in mine:
        names = left[where]
        asking = "which line is this" if len(names) > 1 else f"which of these is the {fact}"
        ask[where] = Asked(where[1], quotes[where], asking, tuple((n, desc[n]) for n in names))
  settled = {where: lines[0] for where, lines in left.items() if len(lines) == 1 and where not in ask}
  return tuple(ret), tuple(ask[where] for where in sorted(ask)), sums(form, fitted(form, kept, settled))

def named(held:dict[str, Any], key:str, roles:tuple[str, ...]) -> dict[str, Any]:
  if not isinstance(got := held.get(key), dict) or set(got) != set(roles):
    raise ValueError(f"model.json must hold {key} naming each of {list(roles)}")
  return got

def wording(parts:dict[str, Any], part:str) -> str:
  if not isinstance(got := parts.get(part), str): raise ValueError(f"model.json must hold the {part} wording as a piece of text")
  try: got.format(**dict.fromkeys(TAKEN[part], ""))
  except (KeyError, IndexError, ValueError) as e:
    raise ValueError(f"the {part} wording in model.json takes something other than {list(TAKEN[part])}") from e
  if missing := [name for name in TAKEN[part] if "{" + name not in got]:
    raise ValueError(f"the {part} wording in model.json leaves out {missing}")
  return got

def shaped() -> Shape:
  held = data("model")
  takes, gives, parts = named(held, "takes", ROLES), named(held, "gives", tuple(r for r, _ in ANSWERS)), named(held, "schema", PARTS)
  schema = Schema(*(wording(parts, part) for part in PARTS))
  line, written_at = text(held, "line_mark", "model.json"), text(held, "text_mark", "model.json")
  if missing := [m for m in (line, written_at) if m not in schema.lists + schema.document]:
    raise ValueError(f"model.json names {missing}, which the wording never writes")
  if not isinstance(start := held.get("word_start"), str) or not start: raise ValueError("model.json must hold word_start as a piece of text")
  return Shape(tuple(text(takes, role, "model.json, under takes") for role in ROLES),
               tuple(text(gives, role, "model.json, under gives") for role, _ in ANSWERS), schema, line, written_at, start)

def reader() -> tuple[Any, Any]:
  for path, flag in ((IT01_MODEL_FILE, "IT01_MODEL_FILE"), (IT01_TOKENISER, "IT01_TOKENISER")):
    if not path: raise ValueError(f"set {flag} to read with a model of your own")
    if not pathlib.Path(path).is_file(): raise ValueError(f"{flag} names {path}, which is not a file")
  return onnxruntime.InferenceSession(IT01_MODEL_FILE, providers=["CPUExecutionProvider"]), tokenizers.Tokenizer.from_file(IT01_TOKENISER)

def figure(quote:str) -> Decimal|None:
  try: return amount(quote)
  except ValueError: return None

def found(document:str) -> tuple[Found, ...]:
  if not (said := words(document)): raise ValueError("the document holds no words")
  ask, shape = wanted(), shaped()
  session, tok = reader()
  size = sizes(session, shape)
  best:dict[tuple[str, int, int], int] = {}
  for few in batched(ask, size["lines"]):
    cuts = windows(tok, said, few, shape, size)
    for idx, (at, cnt) in enumerate(cuts):
      for name, seen in spans(session, tok, said[at:at + cnt], few, shape, size).items():
        for sure, first, last in seen:
          if (at > 0 and first == 0) or (last == cnt and idx < len(cuts) - 1): continue
          key = (name, at + first, at + last)
          best[key] = max(best.get(key, 0), sure)
  ret = []
  for (name, a, b), sure in best.items():
    quote = document[said[a][1]:said[b - 1][2]]
    if (amt := figure(quote)) is not None: ret.append(Found(name, amt, quote, sure, said[a][1]))
  return tuple(sorted(ret, key=lambda f: (-f.sure, f.field)))
