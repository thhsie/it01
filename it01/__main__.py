import pathlib, sys
from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal
from typing import TYPE_CHECKING
from it01.credits import Question, drifted, label
from it01.debits import spending
from it01.labels import Labelled, totals
from it01.form import Form, ending, is_titled, wanted
from it01.helpers import data
from it01.kinds import ADRIFT, Paying, paying, picked, spoken
from it01.keep import Document, answer, apart, case, confirm, dumped, figures, fingerprint, is_given, keep, labelled, loaded, noted, relabelled
from it01.keep import DIFFERS, LACKING, UNCHECKED, ON_LINE, PAID_IN, TITLES, adrift, asking_for, closed, lacking, needing, newly, paid_as
from it01.keep import behind, costed, lines_of, Noted, offering, outgoing, reanswered, spent_as, taken, with_year, worded
from it01.keep import WORDING, at, listed, owned, removed, set_fact, unconfirmed, wording, year_of
from it01.read import read
from it01.rows import Check, currency_of, dropped, entries, is_statement, months
from it01.sheet import sheet, untyped
from it01.tax import Facts, from_json
if TYPE_CHECKING: from it01.local import Asked, Sum, Told

MARKS = {Check.AGREES: "ok", Check.DIFFERS: DIFFERS, Check.UNCHECKED: UNCHECKED}
USAGE = ("usage: it01 FACTS.json\n       it01 read DOCUMENT\n"
         "       it01 rows STATEMENT\n       it01 credits STATEMENT\n       it01 debits STATEMENT\n"
         "       it01 keep FACTS.json\n       it01 local DOCUMENT\n"
         "       it01 confirm FACTS.json FACT\n       it01 add FACTS.json DOCUMENT\n"
         "       it01 show FACTS.json DOCUMENT\n       it01 year FACTS.json YYYY-MM\n"
         "       it01 set FACTS.json FACT VALUE\n       it01 rebuild FACTS.json\n"
         "       it01 remove FACTS.json DOCUMENT\n       it01 unconfirm FACTS.json FACT\n"
         "       it01 answer FACTS.json QUESTION ANSWER\n       it01 change FACTS.json QUESTION KIND\n"
         "       it01 data FACTS.json\n       it01 sheet FACTS.json")

def money(amt:Decimal|None) -> str: return f"{amt:,}" if amt is not None else ""

def to_figures(text:str) -> list[str]: return figures(apart(loaded(text))[0])

def to_proposals(text:str) -> list[str]:
  ret = []
  for p in read(text): ret += [f"{p.fact:<46}{p.amt:>14,}", f"  {p.quote}"]
  return ret or ["no facts found in the document"]

def source(here:pathlib.Path) -> str:
  if here.suffix.lower() != ".pdf": return here.read_text(encoding="utf-8")
  try:
    from it01.local import looked
    from it01.paper import pictured
  except ImportError as e: raise ValueError(f"reading a PDF needs pip install 'it01[pdf,local]' ({e})") from e
  pages = looked(pictured(here))
  if blank := [str(n) for n, page in enumerate(pages, 1) if not page.strip()]:
    raise ValueError(f"nothing could be read on {here.name} page {', '.join(blank)}")
  return "\n\f".join(pages)

def reading(form:Form, text:str) -> tuple[tuple["Told", ...], tuple["Asked", ...], tuple["Sum", ...]]:
  try: from it01.local import found, tells
  except ImportError as e: raise ValueError(f"reading with a model file needs pip install 'it01[local]' ({e})") from e
  return tells(form, found(text))

def shaped(told:tuple["Told", ...], asked:tuple["Asked", ...]) -> tuple[dict[str, tuple[Decimal, str]], list[tuple[str, str]]]:
  seen = {t.fact: (t.amt, t.quote) for t in told}
  return seen, [(f"{q.amt:,} on the line {q.quote}", offering(q.asking, q.lines)) for q in asked]

def to_local(text:str) -> list[str]:
  told, asked, working = reading(wanted(), text)
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
  ret = [f"{e.line + 1:>6}  {e.date:<12}{money(e.paid_out):>14}{money(e.paid_in):>14}{money(e.balance):>14}  {MARKS[e.check]:<15}{e.description}"
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

def to_debits(text:str) -> list[str]:
  if not (found := spending(text)): return ["no money was paid out of the account"]
  ret = []
  for kind, amt in totals(found).items():
    same = [d for d in found if d.kind == kind]
    unsure = sum(1 for d in same if d.check is not Check.AGREES)
    ret.append(f"{kind:<46}{amt:>14,}{len(same):>5} debit" + ("s" if len(same) > 1 else "")
               + (f", {unsure} with no balance that agrees" if unsure else ""))
  return ret

def rewritten(here:pathlib.Path, text:str) -> None:
  spare = here.with_suffix(here.suffix + ".new")
  spare.write_text(text, encoding="utf-8")
  spare.replace(here)

def accepted(here:pathlib.Path, name:str) -> list[str]:
  rewritten(here, confirm(here.read_text(encoding="utf-8"), name))
  return [f"{name} is now a fact in {here.name}"]

def written_in(here:pathlib.Path, name:str, said:str) -> list[str]:
  rewritten(here, set_fact(here.read_text(encoding="utf-8"), name, said))
  return [f"{name} is now a fact in {here.name}" if said.strip() else f"{name} is cleared from {here.name}"]

def taken_back(here:pathlib.Path, name:str) -> list[str]:
  rewritten(here, unconfirmed(here.read_text(encoding="utf-8"), name))
  return [f"{name} is proposed again in {here.name}"]

def dropped_doc(here:pathlib.Path, name:str) -> list[str]:
  rewritten(here, removed(here.read_text(encoding="utf-8"), name))
  return [f"{name} is no longer part of {here.name}"]

def rebuilt(here:pathlib.Path) -> list[str]:
  raw = loaded(here.read_text(encoding="utf-8"))
  if not isinstance(raw, dict): raise ValueError(f"{here.name} is not a case")
  if "proposed" not in raw and not (raw.get("documents") and "version" not in raw):
    apart(raw)
    return [f"{here.name} needs no rebuild"]
  docs, paths = wording(raw, "documents"), wording(raw, "paths")
  if unknown := sorted(set(docs) - set(paths)): raise ValueError(f"these documents have no recorded path, so nothing changed: {', '.join(unknown)}")
  if missing := [paths[d] for d in docs if not pathlib.Path(paths[d]).is_file()]:
    raise ValueError(f"these documents are no longer there, so nothing changed: {', '.join(missing)}")
  kept = {k: v for k, v in raw.items() if k == "year" or k not in ("proposed", *WORDING)}
  kept |= {"sources": {n: said for n, said in wording(raw, "sources").items() if at(kept, n) is not None}}
  answers, lost, skipped, spare = dict(wording(raw, "answers")), [], [], here.with_suffix(here.suffix + ".rebuilt")
  try:
    spare.write_text(dumped(kept) + "\n", encoding="utf-8")
    for doc in docs:
      if (said := added(spare, paths[doc])[0]).endswith("so nothing changed"): skipped.append(said)
    while again := [q for q in apart(loaded(spare.read_text(encoding="utf-8")))[1]["pending"] if q in answers]:
      for question in again:
        try: responded(spare, question, answers.pop(question))
        except ValueError: lost.append(question)
    spare.replace(here)
  finally: spare.unlink(missing_ok=True)
  left = [*lost, *answers]
  ret = [f"{here.name} was read again from its documents"] + (["", "documents skipped"] + [f"  {one}" for one in skipped] if skipped else [])
  return ret + (["", "answers not replayed"] + [f"  {q}" for q in left] if left else [])

def yeared(here:pathlib.Path, first:str) -> list[str]:
  rewritten(here, with_year(here.read_text(encoding="utf-8"), first))
  return [f"{here.name} covers the income year from {first}"]

def matched(held:dict[str, str], asked:str, what:str) -> str:
  hit = [asked] if asked in held else [q for q in held if q.lower().startswith(asked.lower())]
  if len(hit) != 1: raise ValueError(f"{len(hit)} {what} questions match {asked}")
  return hit[0]

def kinded(text:str, question:str, keys:list[str], kind:str) -> tuple[str, list[str]]:
  docs = listed(apart(loaded(text))[1])
  if len({part[0] for k in keys if (part := owned(k, docs))}) > 1:
    raise ValueError(f"{question} was read in more than one document, so say which in words")
  if not PAID_IN.match(question): return text, []
  return relabelled(text, keys, kind, vouched=True), [f"labelled {kind}"]

def told(how:Noted, before:str, after:str) -> list[str]:
  return [f"  proposed {name}" for name in newly(before, after)] + [f"  asked {q}" for q in how.asked]

def responded(here:pathlib.Path, asked:str, said:str) -> list[str]:
  if not (asked := asked.strip()): raise ValueError("the question to answer is blank")
  text = here.read_text(encoding="utf-8")
  pending = apart(loaded(text))[1]["pending"]
  question = matched(pending, asked, "open")
  table, ret, before = spoken("labelling"), [f"answered {question}", f"  {said}"], text
  keys = labelled(text, question) if pending[question] in table.asking.values() and (kind := said.strip()) in picked(table) else []
  taken(question, said, behind(apart(loaded(text))[1], question))
  if (allowed := closed(question, pending[question])) and said.strip() not in allowed:
    raise ValueError(f"answer {question} with one of: {', '.join(allowed)}")
  offered = lines_of(pending[question]) if ON_LINE.fullmatch(question) else []
  if offered and said.strip() in dict(wanted().fields) and said.strip() not in offered:
    raise ValueError(f"answer {question} with one of: {', '.join(offered)}")
  text = answer(text, question, said)
  if keys:
    text, lines = kinded(text, question, keys, kind)
    ret += lines
  if (need := LACKING.fullmatch(question)) and (paid := paid_as(text, need["kind"])):
    text = relabelled(text, paid, said.strip())
    ret += [f"labelled {said.strip()}"]
  text, how = costed(text)
  rewritten(here, text)
  return ret + told(how, before, text)

def changed(here:pathlib.Path, asked:str, said:str) -> list[str]:
  if not (asked := asked.strip()): raise ValueError("the question to change is blank")
  text = here.read_text(encoding="utf-8")
  answers = apart(loaded(text))[1]["answers"]
  question = matched(answers, asked, "answered")
  table, keys, before = spoken("labelling"), labelled(text, question), text
  if not keys or not PAID_IN.match(question) or (kind := said.strip()) not in picked(table):
    raise ValueError(f"only a payment's kind can be changed, to one of: {', '.join(picked(table))}")
  text, lines = kinded(reanswered(text, question, kind), question, keys, kind)
  text, how = costed(text)
  rewritten(here, text)
  return [f"changed {question}"] + lines + told(how, before, text)

def opened(here:pathlib.Path, name:str) -> list[str]:
  held = apart(loaded(here.read_text(encoding="utf-8")))[1]
  if name not in held["paths"]: raise ValueError(f"the case does not say where {name} was read from")
  if not (paper := pathlib.Path(held["paths"][name])).is_file(): raise ValueError(f"{name} is no longer at {paper}")
  if held["texts"].get(fingerprint(paper.read_bytes())) != name: raise ValueError(f"{name} has changed since it was read")
  return source(paper).splitlines()

def paid_out(found:tuple[Labelled, ...], table:Paying, doc:str) -> tuple[list[tuple[str, str]], tuple[tuple[str, str], ...]]:
  kept = tuple(d for d in found if d.check is not Check.DIFFERS)
  sums = totals(kept)
  ret = [(outgoing(amt, sum(1 for d in kept if d.kind == kind), kind, doc), asking_for(table, kind, amt))
         for kind, amt in sums.items() if kind not in table.aside and kind not in table.business]
  return ret, tuple((spent_as(d.amt, d.date, d.description), d.kind) for d in kept if d.kind not in table.aside)

def questioned(questions:tuple[Question, ...]) -> list[tuple[str, str]]:
  return [(worded(q.amt, q.date, q.description), adrift() if q.asking == ADRIFT else q.asking) for q in questions]

def within(year:dict[str, str], found:tuple[Labelled, ...], questions:tuple[Question, ...],
           spent:tuple[Labelled, ...]) -> tuple[tuple[Labelled, ...], tuple[Question, ...], tuple[Labelled, ...], tuple[tuple[str, str], ...]]:
  if not year: return found, questions, spent, ()
  ways, inside = months(tuple(x.date for x in (*found, *spent))), set(year_of(year["from"]))
  def keeps(date:str) -> bool: return (at := ways.get(date)) is None or at in inside
  left = tuple((worded(c.amt, c.date, c.description), "paid in") for c in found if not keeps(c.date))
  left += tuple((spent_as(d.amt, d.date, d.description), "paid out") for d in spent if not keeps(d.date))
  return (tuple(c for c in found if keeps(c.date)), tuple(q for q in questions if keeps(q.date)), tuple(d for d in spent if keeps(d.date)), left)

def added(here:pathlib.Path, document:str) -> list[str]:
  paper = pathlib.Path(document)
  given, held, proposed = apart(loaded(here.read_text(encoding="utf-8")))
  if paper.name in held["documents"]: return [f"{paper.name} was read before, so nothing changed"]
  if (mark := fingerprint(paper.read_bytes())) in held["texts"]:
    return [f"{paper.name} is the same file as {held['texts'][mark]}, so nothing changed"]
  src = source(paper)
  labels:tuple[tuple[str, str], ...] = ()
  paid:tuple[tuple[str, str], ...] = ()
  left:tuple[tuple[str, str], ...] = ()
  currency:str|None = None
  read:tuple[tuple[str, str], ...] = ()
  checks:tuple[tuple[str, str], ...] = ()
  freed:list[str] = []
  hint = ""
  if is_statement(src):
    if (currency := currency_of(src)) and (others := sorted(set(held["currencies"].values()) - {currency})):
      raise ValueError(f"{paper.name} is in {currency}, and this case is in {', '.join(others)}, so nothing was read")
    table = spoken("labelling")
    was = table.prompt.name
    found, questions, spent, left = within(held["year"], *label(src), spending(src))
    asking = questioned(questions + drifted(found, table.feeds))
    asking += [(lacking(kind, fact), needing(table, kind)) for kind, (fact, _) in table.needs.items()
               if any(c.kind == kind for c in found) and not is_given(given, proposed, fact)]
    labels = tuple((worded(c.amt, c.date, c.description), c.kind) for c in found)
    checks = tuple((worded(c.amt, c.date, c.description), MARKS[c.check]) for c in found if c.check is not Check.AGREES)
    if any(asks in table.asking.values() for _, asks in asking): hint = f"answer a payment with one of: {', '.join(picked(table))}"
    out, paid = paid_out(spent, paying(), paper.name)
    asking += out
    freed = [line for kind, amt in totals(found).items() if (why := table.exempt.get(kind))
             for line in (f"  {kind:<32}{amt:>16,}", f"    {why.section:<42}{why.url}")]
  else:
    if not is_titled(form := wanted(), src):
      raise ValueError(f"{paper.name} is neither a bank statement nor a {form.title}, so nothing was read")
    if form.ends and (year := held["year"]) and (end := ending(form, src)) != year["to"]:
      covers = f"covers the income year ending {end}" if end else "does not say which income year it covers"
      raise ValueError(f"{paper.name} {covers}, and this case covers {year['from']} to {year['to']}, so nothing was read")
    told, asked, _ = reading(form, src)
    was, seen, asking = form.name, *shaped(told, asked)
    read = tuple((fact, f"{amt:,} read from {quote}") for fact, (amt, quote) in seen.items())
  entry = Document(name=paper.name, path=str(paper.resolve()), mark=mark, kind=was)
  before = here.read_text(encoding="utf-8")
  text, how = noted(before, entry, asking, labels, paid, left, currency, read, checks)
  text, costs = costed(text)
  rewritten(here, text)
  how = replace(how, asked=how.asked + costs.asked)
  ret = [f"{paper.name} read as {was}"]
  if left: ret += ["", TITLES["outside"]] + [f"  {line}" for line, _ in left]
  if freed: ret += ["", "exempt"] + freed
  if new := newly(before, text): ret += ["", "proposed"] + [f"  {name:<32}{amt:>16,}" for name, amt in new.items()]
  if how.asked: ret += ["", "questions"] + [f"  {question}" for question in how.asked]
  if hint: ret += ["", hint]
  if how.answered: ret += ["", "asked before and answered"] + [f"  {question}" for question in how.answered]
  return ret

def to_data(text:str) -> list[str]: return [dumped(case(text))]

def to_sheet(text:str) -> list[str]:
  f = from_json(Facts, apart(loaded(text))[0])
  table = data("portal")
  ret = [f"{field:<24}{value:>16}" + ("  filled in by the return, check it" if field in table["prefilled"] else "")
         + ("  the total of all rows" if field in table["rows"] else "") for field, value in sheet(f)]
  if notes := untyped(f): ret += ["", "not on the sheet"] + [f"  {note}" for note in notes]
  return ret

VERBS = {"read": to_proposals, "rows": to_transactions, "credits": to_credits, "debits": to_debits, "keep": keep, "local": to_local,
         "data": to_data, "sheet": to_sheet}
ON_CASE:dict[str, tuple[Callable[..., list[str]], int]] = {"confirm": (accepted, 2), "add": (added, 2), "answer": (responded, 3),
                                                           "change": (changed, 3), "show": (opened, 2), "year": (yeared, 2),
                                                           "rebuild": (rebuilt, 1), "remove": (dropped_doc, 2), "unconfirm": (taken_back, 2),
                                                           "set": (written_in, 3)}

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
