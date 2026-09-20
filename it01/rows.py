import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, auto

MONEY = re.compile(r"(?<![\d.,])\(?-?(?:\d{1,3}(?:,\d{3})+\.\d{2}|\d{1,3}(?:\.\d{3})+,\d{2}"
                   r"|\d{1,3}(?: \d{3})+[.,]\d{2}|\d+[.,]\d{2})\)?-?(?![\d.,%])")
DATE = re.compile(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2} [A-Za-z]{3,9} \d{2,4}")
GAP = re.compile(r"\s{2,}")
ZERO = Decimal(0)
SPREAD = 3
HEADING_SPREAD = 8
EXPLAINED = Decimal("0.6")

class Kind(Enum):
  PAID_OUT = auto()
  PAID_IN = auto()
  BALANCE = auto()

class Check(Enum):
  AGREES = auto()
  DIFFERS = auto()
  UNCHECKED = auto()

HEADINGS = {"debit": Kind.PAID_OUT, "debits": Kind.PAID_OUT, "withdrawal": Kind.PAID_OUT, "withdrawals": Kind.PAID_OUT,
            "paid out": Kind.PAID_OUT, "money out": Kind.PAID_OUT, "credit": Kind.PAID_IN, "credits": Kind.PAID_IN,
            "deposit": Kind.PAID_IN, "deposits": Kind.PAID_IN, "paid in": Kind.PAID_IN, "money in": Kind.PAID_IN}

@dataclass(frozen=True)
class Amount:
  value: Decimal
  line: int
  col: int

@dataclass(frozen=True)
class Entry:
  date: str
  description: str
  paid_out: Decimal|None
  paid_in: Decimal|None
  balance: Decimal|None
  check: Check

def to_decimal(text:str) -> Decimal:
  raw = text.strip()
  negative = raw.startswith(("(", "-")) or raw.endswith("-")
  digits = re.sub(r"[()\s-]", "", raw)
  value = Decimal(digits[:-3].replace(",", "").replace(".", "") + "." + digits[-2:])
  return -value if negative else value

def amounts(text:str) -> tuple[Amount, ...]:
  return tuple(Amount(to_decimal(m.group()), line, m.end()) for line, row in enumerate(text.split("\n")) for m in MONEY.finditer(row))

def columns(found:tuple[Amount, ...]) -> tuple[int, ...]:
  ret:list[int] = []
  for col in sorted(a.col for a in found):
    if not any(abs(col - c) <= SPREAD for c in ret): ret.append(col)
  return tuple(ret)

def closest[T](places:tuple[T, ...], col:int, ends:Callable[[T], int], spread:int) -> T|None:
  return min((p for p in places if abs(ends(p) - col) <= spread), key=lambda p: abs(ends(p) - col), default=None)

def nearest(cols:tuple[int, ...], col:int) -> int|None: return closest(cols, col, lambda c: c, SPREAD)

def tally() -> dict[Kind, int]: return {Kind.PAID_OUT: 0, Kind.PAID_IN: 0}

def from_arithmetic(found:tuple[Amount, ...], cols:tuple[int, ...]) -> dict[int, Kind]:
  ret:dict[int, Kind] = {}
  totals:dict[int, dict[Kind, int]] = {}
  for col in cols:
    stack = tuple(a for a in found if abs(a.col - col) <= SPREAD)
    sides:dict[int, dict[Kind, int]] = {}
    hits = moved = 0
    for last, this in zip(stack, stack[1:]):
      if not (delta := this.value - last.value): continue
      moved += 1
      for a in found:
        if abs(a.col - col) <= SPREAD or not last.line < a.line <= this.line or abs(a.value) != abs(delta): continue
        if (seat := nearest(cols, a.col)) is None: continue
        hits += 1
        sides.setdefault(seat, tally())[Kind.PAID_IN if delta > 0 else Kind.PAID_OUT] += 1
        break
    if moved < 2 or hits < EXPLAINED * moved: continue
    ret[col] = Kind.BALANCE
    for side, counted in sides.items():
      into = totals.setdefault(side, tally())
      for kind, n in counted.items(): into[kind] += n
  for side, counted in totals.items():
    if side not in ret and counted[Kind.PAID_OUT] != counted[Kind.PAID_IN]: ret[side] = max(counted, key=lambda kind: counted[kind])
  return ret

def cells(row:str) -> tuple[tuple[str, int], ...]:
  ret, at = [], 0
  for piece in GAP.split(row):
    if not piece: continue
    at = row.index(piece, at) + len(piece)
    ret.append((piece, at))
  return tuple(ret)

def breaks(text:str) -> tuple[int, ...]:
  ret = [0]
  for line, row in enumerate(text.split("\n")):
    if "\f" not in row: continue
    starts = line if row.split("\f", 1)[1].strip() else line + 1
    if starts > ret[-1]: ret.append(starts)
  return tuple(ret)

def leaves(lines:int, starts:tuple[int, ...], found:tuple[Amount, ...]) -> list[tuple[int, int, int, tuple[Amount, ...]]]:
  ret = []
  for i, start in enumerate(starts):
    stop = starts[i + 1] if i + 1 < len(starts) else lines
    ret.append((i, start, stop, tuple(a for a in found if start <= a.line < stop)))
  return ret

def kinds(lines:int, starts:tuple[int, ...], found:tuple[Amount, ...]) -> tuple[tuple[dict[int, Kind], bool], ...]:
  whole = from_arithmetic(found, columns(found))
  ret = []
  for i, start, stop, here in leaves(lines, starts, found):
    own = from_arithmetic(here, columns(here))
    named = own or whole
    if here and not any((col := nearest(tuple(named), a.col)) is not None and named[col] is Kind.BALANCE for a in here): named = {}
    ret.append((named, bool(own)))
  return tuple(ret)

def headings(rows:list[str], starts:tuple[int, ...], found:tuple[Amount, ...], maps:tuple[tuple[dict[int, Kind], bool], ...]) -> tuple[int, int]:
  agree = oppose = 0
  for i, start, stop, here in leaves(len(rows), starts, found):
    named, own = maps[i]
    if not here or not own: continue
    sides = {col: kind for col, kind in named.items() if kind is not Kind.BALANCE}
    votes = []
    for row in rows[start:stop]:
      words = [(word.lower(), ends) for word, ends in cells(row) if word.lower() in HEADINGS]
      said = [(kind, HEADINGS[over[0]]) for col, kind in sides.items()
              if (over := closest(tuple(words), col, lambda w: w[1], HEADING_SPREAD)) is not None]
      votes.append((sum(1 for was, kind in said if was is kind), sum(1 for was, kind in said if was is not kind)))
    most = max((said + against for said, against in votes), default=0)
    top = [vote for vote in votes if vote[0] + vote[1] == most and most]
    if any(said > against for said, against in top) and any(against > said for said, against in top):
      raise ValueError(f"the headings on page {i + 1} disagree about which way the money moved")
    if top: agree, oppose = agree + top[0][0], oppose + top[0][1]
  return agree, oppose

def described(rows:list[str], first:int, last:int) -> str:
  said = " ".join(GAP.sub(" ", DATE.sub(" ", MONEY.sub(" ", rows[i]))).strip() for i in range(first, last + 1))
  return GAP.sub(" ", said).replace("\f", "").strip()

def dated(rows:list[str], first:int, last:int) -> str:
  return next((m.group() for i in range(first, last + 1) if (m := DATE.search(rows[i]))), "")

def settle(rows:list[str], moves:tuple[tuple[Amount, Kind], ...], balance:Amount|None, running:Decimal|None, flip:bool) -> tuple[Entry, Decimal|None]:
  out = sum((abs(a.value) for a, kind in moves if kind is Kind.PAID_OUT), ZERO) if any(k is Kind.PAID_OUT for _, k in moves) else None
  into = sum((abs(a.value) for a, kind in moves if kind is Kind.PAID_IN), ZERO) if any(k is Kind.PAID_IN for _, k in moves) else None
  carried = running + (into or ZERO) - (out or ZERO) if running is not None else None
  if balance is None or carried is None: check = Check.UNCHECKED
  else: check = Check.AGREES if balance.value == carried else Check.DIFFERS
  spans = [a.line for a, _ in moves] + ([balance.line] if balance is not None else [])
  paid_out, paid_in = (into, out) if flip else (out, into)
  entry = Entry(dated(rows, min(spans), max(spans)), described(rows, min(spans), max(spans)),
                paid_out, paid_in, balance.value if balance is not None else None, check)
  return entry, balance.value if balance is not None else running

def entries(text:str) -> tuple[Entry, ...]:
  rows = text.split("\n")
  found = amounts(text)
  starts = breaks(text)
  maps = kinds(len(rows), starts, found)
  if not any(Kind.BALANCE in named.values() for named, _ in maps): raise ValueError("no running balance column in the statement")
  agree, oppose = headings(rows, starts, found, maps)
  if agree == oppose: raise ValueError("the column headings do not say which way the money moved")
  flip = oppose > agree
  ret:list[Entry] = []
  moves:list[tuple[Amount, Kind]] = []
  running:Decimal|None = None
  for a in found:
    named = maps[max(i for i, start in enumerate(starts) if start <= a.line)][0]
    col = nearest(tuple(named), a.col)
    if col is None: continue
    if (kind := named[col]) is not Kind.BALANCE:
      moves.append((a, kind))
      continue
    if not moves and (running is None or running == a.value):
      running = a.value
      continue
    entry, running = settle(rows, tuple(moves), a, running, flip)
    ret.append(entry)
    moves = []
  if moves:
    entry, running = settle(rows, tuple(moves), None, running, flip)
    ret.append(entry)
  return tuple(ret)
