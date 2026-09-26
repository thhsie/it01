import pathlib, sys
from collections.abc import Callable
from decimal import Decimal
from typing import TYPE_CHECKING
from it01.credits import Question, fed, label, spoken, totals
from it01.keep import Document, answer, apart, case, confirm, dumped, figures, fingerprint, is_given, keep, loaded, noted
from it01.read import read
from it01.rows import Check, dropped, entries, is_statement
if TYPE_CHECKING: from it01.local import Asked, Form, Sum, Told

MARKS = {Check.AGREES: "ok", Check.DIFFERS: "does not agree", Check.UNCHECKED: "not checked"}
USAGE = ("usage: it01 FACTS.json\n       it01 read DOCUMENT\n"
         "       it01 rows STATEMENT\n       it01 credits STATEMENT\n"
         "       it01 keep FACTS.json\n       it01 local DOCUMENT\n"
         "       it01 confirm FACTS.json FACT\n       it01 add FACTS.json DOCUMENT\n"
         "       it01 show FACTS.json DOCUMENT\n"
         "       it01 answer FACTS.json QUESTION ANSWER\n       it01 data FACTS.json")

def money(amt:Decimal|None) -> str: return f"{amt:,}" if amt is not None else ""

def to_figures(text:str) -> list[str]: return figures(apart(loaded(text))[0])

def to_proposals(text:str) -> list[str]:
  ret = []
  for p in read(text): ret += [f"{p.fact:<46}{p.amt:>14,}", f"  {p.quote}"]
  return ret or ["no facts found in the document"]

def source(here:pathlib.Path) -> str:
  if here.suffix.lower() != ".pdf": return here.read_text()
  try: from it01.paper import to_text
  except ImportError as e: raise ValueError(f"reading a PDF needs pip install 'it01[pdf]' ({e})") from e
  return to_text(here)

def reading(text:str) -> tuple["Form", tuple["Told", ...], tuple["Asked", ...], tuple["Sum", ...]]:
  try: from it01.local import found, tells, wanted
  except ImportError as e: raise ValueError(f"reading with a model file needs pip install 'it01[local]' ({e})") from e
  form = wanted()
  return (form, *tells(form, found(text)))

def shaped(told:tuple["Told", ...], asked:tuple["Asked", ...]) -> tuple[dict[str, tuple[Decimal, str]], list[tuple[str, str]]]:
  seen = {t.fact: (t.amt, t.quote) for t in told}
  return seen, [(f"{q.amt:,} on the line {q.quote}", f"{q.asking}: " + "; ".join(f"{n} ({d})" for n, d in q.lines)) for q in asked]

def to_local(text:str) -> list[str]:
  _, told, asked, working = reading(text)
  ret = []
  for t in told: ret += [f"{t.fact:<32}{t.amt:>16,}", f"  {t.line}, {t.quote}"]
  if asked:
    ret += ["", "questions"]
    for q in asked:
      ret += [f"  {q.amt:>16,}  {q.asking}"] + [f"    {n:<32}{d}" for n, d in q.lines] + [f"    {q.quote}"]
  if working:
    ret += ["", "the form's own working"]
    ret += [f"  {s.line} says {s.says:,} and adds to {s.adds:,}  " +
            ("ok" if s.agrees else "does not agree" if s.wrong else "not checked") for s in working]
  return ret or ["no facts found in the document"]

def to_transactions(text:str) -> list[str]:
  ret = [f"{e.date:<12}{money(e.paid_out):>14}{money(e.paid_in):>14}{money(e.balance):>14}  {MARKS[e.check]:<15}{e.description}"
         for e in entries(text)]
  if left := dropped(text): ret += [""] + [f"{n} amount{'s' if n > 1 else ''} on page {page} left out" for page, n in left.items()]
  return ret

def to_credits(text:str) -> list[str]:
  found, questions = label(text)
  if not found: return ["no money was paid into the account"]
  ret = []
  for kind, amt in totals(found).items():
    same = [c for c in found if c.kind == kind]
    unsure = sum(1 for c in same if c.check is not Check.AGREES)
    ret.append(f"{kind:<46}{amt:>14,}{len(same):>5} credit" + ("s" if len(same) > 1 else "")
               + (f", {unsure} with no balance that agrees" if unsure else ""))
  if questions: ret += ["", "questions"] + [f"  {q.date:<12}{q.amt:>14,}  {q.asking:<30}{q.description}" for q in questions]
  return ret

def rewritten(here:pathlib.Path, text:str) -> None:
  spare = here.with_suffix(here.suffix + ".new")
  spare.write_text(text)
  spare.replace(here)

def accepted(here:pathlib.Path, name:str) -> list[str]:
  rewritten(here, confirm(here.read_text(), name))
  return [f"{name} is now a fact in {here.name}"]

def responded(here:pathlib.Path, asked:str, said:str) -> list[str]:
  if not (asked := asked.strip()): raise ValueError("the question to answer is blank")
  text = here.read_text()
  pending = list(apart(loaded(text))[1]["pending"])
  hit = [asked] if asked in pending else [q for q in pending if q.lower().startswith(asked.lower())]
  if len(hit) != 1: raise ValueError(f"{len(hit)} open questions match {asked}")
  rewritten(here, answer(text, hit[0], said))
  return [f"answered {hit[0]}", f"  {said}"]

def opened(here:pathlib.Path, name:str) -> list[str]:
  held = apart(loaded(here.read_text()))[1]
  if name not in held["paths"]: raise ValueError(f"the case does not say where {name} was read from")
  if not (paper := pathlib.Path(held["paths"][name])).is_file(): raise ValueError(f"{name} is no longer at {paper}")
  if held["texts"].get(fingerprint(src := source(paper))) != name: raise ValueError(f"{name} has changed since it was read")
  return src.splitlines()

def worded(amt:Decimal, date:str, description:str) -> str: return f"{amt:,} paid in on {date}, {description}"

def questioned(questions:tuple[Question, ...]) -> list[tuple[str, str]]: return [(worded(q.amt, q.date, q.description), q.asking) for q in questions]

def added(here:pathlib.Path, document:str) -> list[str]:
  paper = pathlib.Path(document)
  given, held, proposed = apart(loaded(here.read_text()))
  if paper.name in held["documents"]: return [f"{paper.name} was read before, so nothing changed"]
  src = source(paper)
  if (mark := fingerprint(src)) in held["texts"]: return [f"{paper.name} holds the same text as {held['texts'][mark]}, so nothing changed"]
  seen:dict[str, tuple[Decimal, str]] = {}
  labels:tuple[tuple[str, str], ...] = ()
  if is_statement(src):
    was, _, feeds, _, needs = spoken("labelling")
    found, questions = label(src)
    seen, adrift = fed(found, feeds)
    asking = questioned(questions + adrift)
    asking += [(f"money labelled {kind} came in and the case gives no {fact}", asks) for kind, (fact, asks) in needs.items()
               if any(c.kind == kind for c in found) and not is_given(given, proposed, fact)]
    labels = tuple((worded(c.amt, c.date, c.description), c.kind) for c in found)
  else:
    form, told, asked, _ = reading(src)
    was, seen, asking = form.name, *shaped(told, asked)
  text, how = noted(here.read_text(), seen, Document(name=paper.name, path=str(paper.resolve()), mark=mark, kind=was), asking, labels)
  rewritten(here, text)
  ret = [f"{paper.name} read as {was}"]
  if how.proposed: ret += ["", "proposed"] + [f"  {name:<32}{seen[name][0]:>16,}" for name in how.proposed]
  if how.asked: ret += ["", "questions"] + [f"  {question}" for question in how.asked]
  if how.answered: ret += ["", "asked before and answered"] + [f"  {question}" for question in how.answered]
  return ret

def to_data(text:str) -> list[str]: return [dumped(case(text))]

VERBS = {"read": to_proposals, "rows": to_transactions, "credits": to_credits, "keep": keep, "local": to_local, "data": to_data}
ON_CASE:dict[str, tuple[Callable[..., list[str]], int]] = {"confirm": (accepted, 2), "add": (added, 2), "answer": (responded, 3),
                                                           "show": (opened, 2)}

def main() -> int:
  args = sys.argv[1:]
  named, on_case = (VERBS.get(args[0]), ON_CASE.get(args[0])) if args else (None, None)
  rest = args[1:] if named or on_case else args
  if len(rest) != (on_case[1] if on_case else 1):
    print(USAGE, file=sys.stderr)
    return 2
  here = pathlib.Path(rest[0])
  try: lines = on_case[0](here, *rest[1:]) if on_case else (named or to_figures)(source(here))
  except (OSError, ValueError) as e:
    print(f"error: {e}", file=sys.stderr)
    return 1
  print("\n".join(lines))
  return 0

if __name__ == "__main__": sys.exit(main())
