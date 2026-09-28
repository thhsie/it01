from it01.helpers import data, instruction
from it01.kinds import prompted
from it01.labels import Labelled, Moved, labelled
from it01.rows import entries

def spent(text:str) -> Moved: return tuple((e, e.paid_out) for e in entries(text) if e.paid_out is not None)

def spending(text:str) -> tuple[Labelled, ...]:
  if not (paid := spent(text)): return ()
  return labelled(paid, prompted("paying", data("paying")), instruction("paying"))
