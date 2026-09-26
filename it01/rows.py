import itertools, re
from collections.abc import Callable
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import Enum, auto
from it01.tax import to_decimal

MONEY = re.compile(r"(?<![\d.,])\(?-?(?:\d{1,3}(?:,\d{3})+\.\d{2}|\d{1,3}(?:\.\d{3})+,\d{2}"
                   r"|\d{1,3}(?: \d{3})+[.,]\d{2}|\d+[.,]\d{2})\)?-?(?![\d.,%])")
DATE = re.compile(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2} [A-Za-z]{3,9} \d{2,4}")
GAP = re.compile(r"\s{2,}")
LEADING = re.compile(rf"^\s*(?:(?:{DATE.pattern})\s*)+")
NUMERIC = re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2}|\d{4})")
WORDED = re.compile(r"(\d{1,2}) ([A-Za-z]+) (\d{2}|\d{4})")
MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")
ORDER = {(True, False): 2, (False, True): 1}
SIGN = re.compile(r"[()-]")
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
  line: int

def to_signed(text:str) -> Decimal:
  raw = text.strip()
  value = to_decimal(SIGN.sub("", raw))
  return -value if raw.startswith(("(", "-")) or raw.endswith("-") else value

def amounts(text:str) -> tuple[Amount, ...]:
  return tuple(Amount(to_signed(m.group()), line, m.end()) for line, row in enumerate(text.split("\n")) for m in MONEY.finditer(row))

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
  said = " ".join(LEADING.sub("", piece) for i in range(first, last + 1) for piece, _ in cells(MONEY.sub(" ", rows[i])))
  return GAP.sub(" ", said).replace("\f", "").strip()

def dated(rows:list[str], first:int, last:int) -> str:
  return next((m.group() for i in range(first, last + 1) for piece, _ in cells(rows[i]) if (m := DATE.match(piece.strip()))), "")

def settle(rows:list[str], moves:tuple[tuple[Amount, Kind], ...], balance:Amount|None, running:Decimal|None, flip:bool) -> tuple[Entry, Decimal|None]:
  out = sum((abs(a.value) for a, kind in moves if kind is Kind.PAID_OUT), ZERO) if any(k is Kind.PAID_OUT for _, k in moves) else None
  into = sum((abs(a.value) for a, kind in moves if kind is Kind.PAID_IN), ZERO) if any(k is Kind.PAID_IN for _, k in moves) else None
  carried = running + (into or ZERO) - (out or ZERO) if running is not None else None
  if balance is None or carried is None: check = Check.UNCHECKED
  else: check = Check.AGREES if balance.value == carried else Check.DIFFERS
  spans = [a.line for a, _ in moves] + ([balance.line] if balance is not None else [])
  first, last = min(spans), max(spans)
  paid_out, paid_in = (into, out) if flip else (out, into)
  entry = Entry(dated(rows, first, last), described(rows, first, last),
                paid_out, paid_in, balance.value if balance is not None else None, check, first)
  return entry, balance.value if balance is not None else running

def balanced(maps:tuple[tuple[dict[int, Kind], bool], ...]) -> bool: return any(Kind.BALANCE in named.values() for named, _ in maps)

def scanned(text:str) -> tuple[list[str], tuple[Amount, ...], tuple[int, ...], tuple[tuple[dict[int, Kind], bool], ...]]:
  rows = text.split("\n")
  found = amounts(text)
  starts = breaks(text)
  return rows, found, starts, kinds(len(rows), starts, found)

def is_statement(text:str) -> bool:
  *_, maps = scanned(text)
  return balanced(maps)

def dropped(text:str) -> dict[int, int]:
  rows, found, starts, maps = scanned(text)
  ret = {}
  for i, start, stop, here in leaves(len(rows), starts, found):
    if left := sum(1 for a in here if nearest(tuple(maps[i][0]), a.col) is None): ret[i + 1] = left
  return ret

def entries(text:str) -> tuple[Entry, ...]:
  rows, found, starts, maps = scanned(text)
  if not balanced(maps): raise ValueError("no running balance column in the statement")
  agree, oppose = headings(rows, starts, found, maps)
  if agree == oppose: raise ValueError("the column headings do not say which way the money moved")
  flip = oppose > agree
  ret:list[Entry] = []
  moves:list[tuple[Amount, Kind]] = []
  running:Decimal|None = None
  settled:dict[Kind, list[Decimal]] = {}
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
    for was, kind in moves: settled.setdefault(kind, []).append(abs(was.value))
    moves = []
  summed = all(len(above := settled.get(kind, [])) >= 2 and sum(above, ZERO) == abs(a.value) for a, kind in moves)
  if moves and (not summed or dated(rows, moves[0][0].line, moves[-1][0].line)):
    entry, running = settle(rows, tuple(moves), None, running, flip)
    ret.append(entry)
  return tuple(itertools.accumulate(ret, lambda was, entry: entry if entry.date else replace(entry, date=was.date)))

def year(said:str) -> int: return int(said) + (2000 if len(said) == 2 else 0)

def is_day(said:str) -> bool: return 1 <= int(said) <= 31

def month_number(word:str) -> int: return next((n for n, full in enumerate(MONTHS, 1) if word.lower() in (full, full[:3])), 0)

def month_of(date:str, place:int) -> str|None:
  if (m := WORDED.fullmatch(date)) and (at := month_number(m[2])) and is_day(m[1]): return f"{year(m[3])}-{at:02d}"
  if not (m := NUMERIC.fullmatch(date)) or not place: return None
  return f"{year(m[3])}-{int(m[place]):02d}" if 1 <= int(m[place]) <= 12 and is_day(m[3 - place]) else None

def months(dates:tuple[str, ...]) -> dict[str, str|None]:
  split = [(int(m[1]), int(m[2])) for d in dates if (m := NUMERIC.fullmatch(d))]
  place = ORDER.get((any(12 < a <= 31 for a, _ in split), any(12 < b <= 31 for _, b in split)), 0)
  return {d: month_of(d, place) for d in dates}
