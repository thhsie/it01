import math, pathlib, re
import numpy as np, onnxruntime, tokenizers
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from it01.helpers import IT01_MODEL_FILE, IT01_TOKENISER, data
from it01.read import AMOUNTS, amount

WORD = re.compile(r"\w+|[^\w\s]")
WORD_START = "▁"
SURE = 50
QUARTER = 4
TAKES = ("input_ids", "attention_mask", "tw_idx", "tw_mask", "q_idx", "q_mask")
GIVES = {"indices": 4, "pair_logits": 3, "valid_mask": 3}
LIMIT = 700

@dataclass(frozen=True)
class Found:
  fact: str
  amt: Decimal
  quote: str
  sure: int

def words(text:str) -> tuple[tuple[str, int, int], ...]:
  return tuple((m.group().lower(), m.start(), m.end()) for m in WORD.finditer(text))

def schema(fields:dict[str, str]) -> str:
  return ("([P] entities" + "".join(f"[DESCRIPTION] {name}: {means}" for name, means in fields.items())
          + " (" + "".join(f"[E] {name}" for name in fields) + " ) )")

def written(fields:dict[str, str], said:tuple[tuple[str, int, int], ...]) -> str:
  # the model was trained on text ending in a period
  return schema(fields) + "[SEP_TEXT] " + " ".join(w for w, _, _ in said) + " ."

def marker(tok:Any, name:str) -> int:
  if (at := tok.token_to_id(name)) is None: raise ValueError(f"the tokeniser has no {name}, so it does not go with this model")
  return int(at)

def prompt(tok:Any, said:tuple[tuple[str, int, int], ...], fields:dict[str, str]) -> tuple[list[int], list[int], list[int]]:
  coded = tok.encode(written(fields, said), add_special_tokens=False)
  sep, mark = marker(tok, "[SEP_TEXT]"), marker(tok, "[E]")
  if sep not in coded.ids: raise ValueError("the tokeniser did not mark where the document starts")
  starts = [i for i in range(coded.ids.index(sep) + 1, len(coded.ids)) if coded.tokens[i].startswith(WORD_START)]
  if len(starts) != len(said) + 1:
    raise ValueError(f"the tokeniser split {len(said)} words into {max(len(starts) - 1, 0)}, so the wording cannot be traced")
  markers = [i for i, x in enumerate(coded.ids) if x == mark]
  if len(markers) != len(fields): raise ValueError(f"the tokeniser marked {len(markers)} of {len(fields)} fields")
  return coded.ids, starts[:len(said)], markers

def room(tok:Any, said:tuple[tuple[str, int, int], ...], fields:dict[str, str], cap:int) -> int:
  low, high = 0, len(said)
  while low < high:
    mid = (low + high + 1) // 2
    if len(tok.encode(written(fields, said[:mid]), add_special_tokens=False).ids) <= cap: low = mid
    else: high = mid - 1
  if not low: raise ValueError(f"the field descriptions leave no room for the document in a model file that takes {cap} tokens")
  return low

def windows(tok:Any, said:tuple[tuple[str, int, int], ...], fields:dict[str, str], size:dict[str, int]) -> list[tuple[int, int]]:
  ret, at = [], 0
  while at < len(said):
    cnt = room(tok, said[at:at + size["tw_idx"]], fields, size["input_ids"])
    ret.append((at, cnt))
    if at + cnt >= len(said): return ret
    at += max(cnt - max(cnt // QUARTER, 1), 1)
  return ret

def sizes(session:Any) -> dict[str, int]:
  ret = {}
  for d in session.get_inputs():
    if len(d.shape) < 2: raise ValueError(f"the model file takes {d.name} in {len(d.shape)} dimensions and this gives 2")
    if not isinstance(size := d.shape[1], int): raise ValueError(f"the model file leaves {d.name} unsized, and this reads a model of fixed size")
    ret[d.name] = size
  if set(ret) != set(TAKES): raise ValueError(f"the model file wants {sorted(ret)} and this gives {list(TAKES)}")
  return ret

def filled(values:list[int], size:int, name:str) -> tuple[np.ndarray, np.ndarray]:
  if len(values) > size: raise ValueError(f"this needs room for {len(values)} {name} and the model file takes {size}")
  spare = size - len(values)
  return np.array([values + [0] * spare], dtype=np.int64), np.array([[True] * len(values) + [False] * spare])

def feed(size:dict[str, int], ids:list[int], starts:list[int], markers:list[int]) -> dict[str, np.ndarray]:
  tokens, attention = filled(ids, size["input_ids"], "tokens")
  spots, kept = filled(starts, size["tw_idx"], "words")
  queries, asked = filled(markers, size["q_idx"], "fields")
  return {"input_ids": tokens, "attention_mask": attention.astype(np.int64), "tw_idx": spots,
          "tw_mask": kept, "q_idx": queries, "q_mask": asked}

def answer(session:Any, fed:dict[str, np.ndarray]) -> dict[str, np.ndarray]:
  names = [d.name for d in session.get_outputs()]
  if missing := sorted(set(GIVES) - set(names)): raise ValueError(f"the model file answers with {names} and this reads {missing}")
  ret = dict(zip(names, session.run(None, fed)))
  for name, dims in GIVES.items():
    if ret[name].ndim != dims: raise ValueError(f"the model file gives {name} in {ret[name].ndim} dimensions and this reads {dims}")
  return ret

def score(logit:Any) -> int: return round(100 / (1 + math.exp(-max(min(logit, LIMIT), -LIMIT))))

def spans(session:Any, tok:Any, said:tuple[tuple[str, int, int], ...], fields:dict[str, str],
          size:dict[str, int]) -> dict[str, list[tuple[int, int, int]]]:
  ids, starts, markers = prompt(tok, said, fields)
  out = answer(session, feed(size, ids, starts, markers))
  ret:dict[str, list[tuple[int, int, int]]] = {name: [] for name in fields}
  for q, name in enumerate(fields):
    for c in range(out["indices"].shape[2]):
      if not out["valid_mask"][0][q][c]: continue
      sure = score(out["pair_logits"][0][q][c])
      first, last = int(out["indices"][0][q][c][0]), int(out["indices"][0][q][c][1])
      if sure < SURE or first >= last or last > len(said): continue
      ret[name].append((sure, first, last))
  return ret

def batched(fields:dict[str, str], size:int) -> list[dict[str, str]]:
  names = list(fields)
  return [{name: fields[name] for name in names[at:at + size]} for at in range(0, len(names), size)]

def wanted() -> dict[str, str]:
  held = data("reading").get("fields")
  if not isinstance(held, dict) or not held or not all(isinstance(v, str) and v.strip() for v in held.values()):
    raise ValueError("reading.json must hold fields as an object of descriptions")
  if unknown := sorted(set(held) - set(AMOUNTS)): raise ValueError(f"reading.json names facts the package does not know {unknown}")
  return held

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
  ask = wanted()
  session, tok = reader()
  size = sizes(session)
  best:dict[tuple[str, int, int], int] = {}
  for few in batched(ask, size["q_idx"]):
    cuts = windows(tok, said, few, size)
    for idx, (at, cnt) in enumerate(cuts):
      for name, seen in spans(session, tok, said[at:at + cnt], few, size).items():
        for sure, first, last in seen:
          if (at > 0 and first == 0) or (last == cnt and idx < len(cuts) - 1): continue
          key = (name, at + first, at + last)
          best[key] = max(best.get(key, 0), sure)
  ret = []
  for (name, a, b), sure in best.items():
    quote = document[said[a][1]:said[b - 1][2]]
    if (amt := figure(quote)) is not None: ret.append(Found(name, amt, quote, sure))
  return tuple(sorted(ret, key=lambda f: (-f.sure, f.fact)))
