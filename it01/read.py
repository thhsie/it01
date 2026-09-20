import json, re
from dataclasses import dataclass
from decimal import Decimal
from it01.helpers import instruction
from it01.llm import ask
from it01.tax import Facts, amount_names, is_amount

AMOUNTS = amount_names(Facts)
FIGURE = re.compile(r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?")

@dataclass(frozen=True)
class Proposal:
  fact: str
  amt: Decimal
  quote: str

def figures(line:str) -> set[Decimal]: return {Decimal(m.replace(",", "")) for m in FIGURE.findall(line)}

def amount(raw:object) -> Decimal:
  if not FIGURE.fullmatch(text := str(raw).strip()): raise ValueError(f"not an amount {raw}")
  if not is_amount(value := Decimal(text.replace(",", ""))): raise ValueError(f"invalid amount {raw}")
  return value

def proposals(document:str, reply:str) -> tuple[Proposal, ...]:
  try: raw = json.loads(reply, parse_float=Decimal)
  except json.JSONDecodeError: raise ValueError(f"the model did not answer with JSON {reply}") from None
  if not isinstance(raw, list): raise ValueError(f"the model must answer with a JSON list, not {type(raw).__name__}")
  lines = {line.strip() for line in document.splitlines() if line.strip()}
  ret = []
  for item in raw:
    if not isinstance(item, dict): raise ValueError(f"every proposal must be a JSON object, not {type(item).__name__}")
    if not isinstance(fact := item.get("fact"), str) or fact not in AMOUNTS: raise ValueError(f"unknown fact {fact}")
    amt = amount(item.get("amount"))
    if not isinstance(quote := item.get("quote"), str) or (line := quote.strip()) not in lines:
      raise ValueError(f"the quote for {fact} is not a line of the document {quote}")
    if amt not in figures(line): raise ValueError(f"the line quoted for {fact} does not show {amt}")
    ret.append(Proposal(fact, amt, line))
  return tuple(ret)

def read(document:str) -> tuple[Proposal, ...]:
  try: asked = instruction().format(facts=", ".join(AMOUNTS))
  except (IndexError, KeyError) as e: raise ValueError(f"the instruction in reading.json uses a brace that is not {{facts}} {e}") from e
  return proposals(document, ask(asked, document))
