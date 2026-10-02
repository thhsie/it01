import pathlib, sys
from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal
from typing import TYPE_CHECKING
from it01.asks import Tables, is_inside, kept_asks, months_of, proposals, questions, tables, worded
from it01.credits import label
from it01.debits import spending
from it01.kinds import spoken
from it01.labels import Labelled, totals
from it01.form import Form, ending, is_titled, wanted
from it01.helpers import data
from it01.held import AGREES, DIFFERS, RECORDS, UNCHECKED, VERSION, Case, Document, Line, Payment, Reading, dumped, loaded, opened, texts, written
from it01.keep import answered, case, confirm, figures, fingerprint, forgot, keep, noted, remember, removed, set_fact, unconfirmed, with_year
from it01.read import read
from it01.rows import Check, currency_of, dropped, entries, is_statement, months
from it01.sheet import sheet, untyped
from it01.tax import Facts, from_json, summed
if TYPE_CHECKING: from it01.local import Asked, Sum, Told

MARKS = {Check.AGREES: AGREES, Check.DIFFERS: DIFFERS, Check.UNCHECKED: UNCHECKED}
OLD = ("proposed", "texts", "paths", "asked", "labels", "paid", "outside", "currencies", "read", "checks", "answers", "pending")
USAGE = ("usage: it01 FACTS.json\n       it01 read DOCUMENT\n"
         "       it01 rows STATEMENT\n       it01 credits STATEMENT\n       it01 debits STATEMENT\n"
         "       it01 keep FACTS.json\n       it01 local DOCUMENT\n"
         "       it01 confirm FACTS.json FACT\n       it01 add FACTS.json DOCUMENT\n"
         "       it01 show FACTS.json DOCUMENT\n       it01 year FACTS.json YYYY-MM\n"
         "       it01 set FACTS.json FACT VALUE\n       it01 rebuild FACTS.json\n"
         "       it01 remove FACTS.json DOCUMENT\n       it01 unconfirm FACTS.json FACT\n"
         "       it01 remember FACTS.json PAYMENT\n       it01 answer FACTS.json QUESTION ANSWER\n       it01 forget FACTS.json QUESTION\n"
         "       it01 data FACTS.json\n       it01 sheet FACTS.json")

def money(amt:Decimal|None) -> str: return f"{amt:,}" if amt is not None else ""

def to_figures(text:str) -> list[str]: return figures(opened(loaded(text)).given)

def to_proposals(text:str) -> list[str]:
  ret = []
  for p in read(text): ret += [f"{p.fact:<46}{p.amt:>14,}", f"  {p.quote}"]
  return ret or ["the document has no facts that the engine can read"]

def source(here:pathlib.Path) -> str:
  if here.suffix.lower() != ".pdf": return here.read_text(encoding="utf-8")
  try:
    from it01.local import looked
    from it01.paper import pictured
  except ImportError as e: raise ValueError(f"to read a PDF, install the extras with pip install 'it01[pdf,local]' ({e})") from e
  pages = looked(pictured(here))
  if blank := [str(n) for n, page in enumerate(pages, 1) if not page.strip()]:
    raise ValueError(f"the engine found no text on {here.name} page {', '.join(blank)}")
  return "\n\f".join(pages)

def reading(form:Form, text:str) -> tuple[tuple["Told", ...], tuple["Asked", ...], tuple["Sum", ...]]:
  try: from it01.local import found, tells
  except ImportError as e: raise ValueError(f"to read with a model file, install the extra with pip install 'it01[local]' ({e})") from e
  return tells(form, found(text))

def to_local(text:str) -> list[str]:
  told, asked, working = reading(wanted(), text)
  ret = []
  for t in told: ret += [f"{t.fact:<32}{t.amt:>16,}", f"  {t.line}, {t.quote}"]
  if asked:
    ret += ["", "questions"]
    for q in asked:
      ret += [f"  {q.amt:>16,}  {q.asking}"] + [f"    {n:<32}{d}" for n, d in q.lines] + [f"    {q.quote}"]
  if working:
    ret += ["", "the totals on the form"]
    ret += [f"  {s.line} says {s.says:,} and adds to {s.adds:,}  " +
            ("agrees" if s.agrees else "does not agree" if s.wrong else "no check") for s in working]
  return ret or ["the document has no facts that the engine can read"]

def to_transactions(text:str) -> list[str]:
  ret = [f"{e.line + 1:>6}  {e.date:<12}{money(e.paid_out):>14}{money(e.paid_in):>14}{money(e.balance):>14}  {MARKS[e.check]:<15}{e.description}"
         for e in entries(text)]
  if left := dropped(text): ret += [""] + [f"the engine did not use {n} amount{'s' if n > 1 else ''} on page {page}" for page, n in left.items()]
  return ret

def to_credits(text:str) -> list[str]:
  if not (found := label(text)): return ["the statement shows no money paid into the account"]
  ret = []
  for kind, amt in totals(found).items():
    same = [c for c in found if c.kind == kind]
    unsure = sum(1 for c in same if c.check is not Check.AGREES)
    ret.append(f"{kind:<46}{amt:>14,}{len(same):>5} credit" + ("s" if len(same) > 1 else "")
               + (f", {unsure} with a balance that does not agree or has no check" if unsure else ""))
  asking = spoken("labelling").asking
  if unclear := [c for c in found if c.kind in asking]:
    ret += ["", "questions"] + [f"  {c.date:<12}{c.amt:>14,}  {asking[c.kind]:<30}{c.description}" for c in unclear]
  return ret

def to_debits(text:str) -> list[str]:
  if not (found := spending(text)): return ["the statement shows no money paid out of the account"]
  ret = []
  for kind, amt in totals(found).items():
    same = [d for d in found if d.kind == kind]
    unsure = sum(1 for d in same if d.check is not Check.AGREES)
    ret.append(f"{kind:<46}{amt:>14,}{len(same):>5} debit" + ("s" if len(same) > 1 else "")
               + (f", {unsure} with a balance that does not agree or has no check" if unsure else ""))
  return ret

def rewritten(here:pathlib.Path, held:Case) -> None:
  spare = here.with_suffix(here.suffix + ".new")
  spare.write_text(written(held), encoding="utf-8")
  spare.replace(here)

def held_in(here:pathlib.Path) -> Case: return opened(loaded(here.read_text(encoding="utf-8")))

def told(before:Case, after:Case, t:Tables) -> list[str]:
  was, now = proposals(before, t)[0], proposals(after, t)[0]
  def waiting(held:Case) -> list[str]:
    return [q.subject for q in questions(held, t, proposals(held, t)[0]) if held.decisions.get(q.subject) is None]
  asked = set(waiting(before))
  return ([f"  new proposed figure {name:<20}{amt:>16,}" for name, amt in now.items() if was.get(name) != amt]
          + [f"  new question {subject}" for subject in waiting(after) if subject not in asked])

def changed_by(here:pathlib.Path, work:Callable[[Case, Tables], Case], *said:str) -> list[str]:
  before, t = held_in(here), tables()
  rewritten(here, after := work(before, t))
  return [*said] + told(before, after, t)

def accepted(here:pathlib.Path, name:str) -> list[str]:
  return changed_by(here, lambda held, t: confirm(held, t, name), f"{name} is a fact in {here.name}")

def written_in(here:pathlib.Path, name:str, said:str) -> list[str]:
  done = f"{name} is a fact in {here.name}" if said.strip() else f"{here.name} has no figure for {name}"
  return changed_by(here, lambda held, t: set_fact(held, t, name, said), done)

def taken_back(here:pathlib.Path, name:str) -> list[str]:
  return changed_by(here, lambda held, t: unconfirmed(held, name), f"{name} is a proposed figure again in {here.name}")

def dropped_doc(here:pathlib.Path, name:str) -> list[str]:
  return changed_by(here, lambda held, t: removed(held, t, name), f"{name} is not part of {here.name}")

def yeared(here:pathlib.Path, first:str) -> list[str]:
  return changed_by(here, lambda held, t: with_year(held, first), f"the income year of {here.name} starts in {first}")

def matched(held:list[str], asked:str, what:str) -> str:
  if not (asked := asked.strip()): raise ValueError(f"type the name of one of the {what}")
  hit = [asked] if asked in held else [q for q in held if q.lower().startswith(asked.lower())]
  if len(hit) != 1: raise ValueError(f"{len(hit)} {what} start with {asked}. Type more of the name, until only one starts with it")
  return hit[0]

def subjects(held:Case, t:Tables) -> list[str]:
  asked = [q.subject for q in questions(held, t, proposals(held, t)[0]) + kept_asks(held, t)]
  return list(dict.fromkeys(asked + [*held.payments, *held.readings]))

def responded(here:pathlib.Path, typed:str, said:str) -> list[str]:
  subject = matched(subjects(held_in(here), tables()), typed, "questions, payments or readings")
  return changed_by(here, lambda held, t: answered(held, t, subject, said), f"your answer to {subject}", f"  {said.strip()}")

def remembered_for(here:pathlib.Path, typed:str) -> list[str]:
  key = matched(list(held_in(here).payments), typed, "payments")
  return changed_by(here, lambda held, t: remember(held, key), f"the answer for {key} applies to all payments with the same words")

def forgotten(here:pathlib.Path, typed:str) -> list[str]:
  subject = matched(list(held_in(here).decisions), typed, "answers")
  return changed_by(here, lambda held, t: forgot(held, t, subject), f"the engine removed your answer for {subject}")

def opened_doc(here:pathlib.Path, name:str) -> list[str]:
  held = held_in(here)
  if not (doc := held.documents.get(name)): raise ValueError(f"the case does not show the location of {name}")
  if not (paper := pathlib.Path(doc.path)).is_file(): raise ValueError(f"{name} is not at {paper}")
  if fingerprint(paper.read_bytes()) != doc.mark: raise ValueError(f"{name} changed after the engine read it")
  return source(paper).splitlines()

def payments_of(name:str, way:str, found:tuple[Labelled, ...], ways:dict[str, str|None]) -> list[tuple[str, Payment]]:
  paid = [Payment(name, way, c.amt, c.date, c.description, c.kind, MARKS[c.check], ways[c.date]) for c in found]
  return [(worded(p), p) for p in paid]

def with_document(held:Case, t:Tables, paper:pathlib.Path, mark:str, src:str) -> Case:
  name, path = paper.name, str(paper.resolve())
  if is_statement(src):
    if (currency := currency_of(src)) and (others := sorted({d.currency for d in held.documents.values() if d.currency} - {currency})):
      raise ValueError(f"{name} is in {currency}, and this case is in {', '.join(others)}. The engine did not read {name}")
    found, spent = label(src), spending(src)
    ways = months(tuple(x.date for x in (*found, *spent)))
    paid = payments_of(name, "in", found, ways) + payments_of(name, "out", spent, ways)
    return noted(held, name, Document(t.into.prompt.name, path, mark, currency), paid, [], [])
  if not is_titled(form := wanted(), src): raise ValueError(f"{name} is not a bank statement or a {form.title}. The engine did not read {name}")
  end = ending(form, src) if form.ends else None
  if form.ends and (year := held.year) and end != year["to"]:
    covers = f"is for the income year that ends in {end}" if end else "does not show its income year"
    raise ValueError(f"{name} {covers}, and this case is for {year['from']} to {year['to']}. The engine did not read {name}")
  seen, asked, _ = reading(form, src)
  read = list({r.fact: Reading(name, r.fact, r.amt, r.quote) for r in seen}.values())
  lines = [(f"{q.amt:,} on the line {q.quote}", Line(name, q.amt, q.quote, q.asking, tuple(q.lines))) for q in asked]
  return noted(held, name, Document(form.name, path, mark, ends=end), [], read, lines)

def added(here:pathlib.Path, document:str) -> list[str]:
  paper, held, t = pathlib.Path(document), held_in(here), tables()
  if paper.name in held.documents: return [f"{paper.name} is in the case. The case did not change"]
  mark = fingerprint(paper.read_bytes())
  if same := next((n for n, d in held.documents.items() if d.mark == mark), None):
    return [f"{paper.name} is the same file as {same}. The case did not change"]
  after = with_document(held, t, paper, mark, source(paper))
  rewritten(here, after)
  ret = [f"{paper.name} is a {after.documents[paper.name].kind}"]
  months = months_of(after)
  if left := [k for k, p in after.payments.items() if p.document == paper.name and not is_inside(p, months)]:
    ret += ["", "not counted, with a date that is not in the income year"] + [f"  {k}" for k in left]
  own = [p for p in after.payments.values() if p.document == paper.name and p.way == "in"]
  if freed := summed([(p.label, p.amount) for p in own if p.label in t.into.exempt]):
    ret += ["", "exempt"] + [line for kind, amt in freed.items() for line in (f"  {kind:<32}{amt:>16,}",
                                                                               f"    {t.into.exempt[kind].section:<42}{t.into.exempt[kind].url}")]
  return ret + ["", *changes] if (changes := told(held, after, t)) else ret

def rebuilt(here:pathlib.Path) -> list[str]:
  raw = loaded(here.read_text(encoding="utf-8"))
  if not isinstance(raw, dict): raise ValueError(f"{here.name} is not a case file")
  docs = raw.get("documents") or {}
  paths = texts(raw.get("paths", {}), "paths") | {n: d["path"] for n, d in docs.items() if isinstance(d, dict) and isinstance(d.get("path"), str)}
  if unknown := sorted(set(docs) - set(paths)):
    raise ValueError(f"the case does not show the location of these documents, and the case did not change: {', '.join(unknown)}")
  if missing := [paths[d] for d in docs if not pathlib.Path(paths[d]).is_file()]:
    raise ValueError(f"these documents are not at their location, and the case did not change: {', '.join(missing)}")
  current = raw.get("version") == VERSION
  given = {k: v for k, v in raw.items() if k not in RECORDS and k not in OLD}
  decisions = texts(raw.get("decisions", {}), "decisions") if current else {}
  kept = opened(given | {"version": VERSION} | {k: raw[k] for k in ("year", "sources", "confirmed") if raw.get(k)})
  held, t, skipped = kept, tables(), []
  for doc in docs:
    paper = pathlib.Path(paths[doc])
    mark = fingerprint(paper.read_bytes())
    if same := next((n for n, d in held.documents.items() if d.mark == mark), None):
      skipped.append(f"{paper.name} is the same file as {same}")
      continue
    held = with_document(held, t, paper, mark, source(paper))
  known = set(subjects(held := replace(held, decisions=decisions), t))
  lost = [s for s in decisions if s not in known]
  if wordings := raw.get("answers"): lost.append(f"answers from a previous version: {len(wordings)}")
  rewritten(here, replace(held, decisions={s: said for s, said in decisions.items() if s in known}))
  ret = [f"the engine read the documents of {here.name} again"] + (["", "documents not read"] + [f"  {one}" for one in skipped] if skipped else [])
  return ret + (["", "answers that the case did not keep"] + [f"  {q}" for q in lost] if lost else [])

def to_keep(text:str) -> list[str]: return keep(opened(loaded(text)), tables())

def to_data(text:str) -> list[str]: return [dumped(case(opened(loaded(text)), tables()))]

def to_sheet(text:str) -> list[str]:
  f = from_json(Facts, opened(loaded(text)).given)
  table = data("portal")
  ret = [f"{field:<24}{value:>16}" + ("  the return fills in this field, examine it" if field in table["prefilled"] else "")
         + ("  the total of all rows" if field in table["rows"] else "") for field, value in sheet(f)]
  if notes := untyped(f): ret += ["", "not on the sheet"] + [f"  {note}" for note in notes]
  return ret

VERBS = {"read": to_proposals, "rows": to_transactions, "credits": to_credits, "debits": to_debits, "keep": to_keep, "local": to_local,
         "data": to_data, "sheet": to_sheet}
ON_CASE:dict[str, tuple[Callable[..., list[str]], int]] = {"confirm": (accepted, 2), "add": (added, 2), "answer": (responded, 3),
                                                           "forget": (forgotten, 2), "show": (opened_doc, 2), "year": (yeared, 2),
                                                           "rebuild": (rebuilt, 1), "remove": (dropped_doc, 2), "unconfirm": (taken_back, 2),
                                                           "set": (written_in, 3), "remember": (remembered_for, 2)}

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
