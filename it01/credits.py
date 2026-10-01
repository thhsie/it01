from it01.helpers import instruction
from it01.kinds import spoken
from it01.labels import Labelled, Moved, labelled
from it01.rows import entries

def received(text:str) -> Moved: return tuple((e, e.paid_in) for e in entries(text) if e.paid_in is not None)

def label(text:str) -> tuple[Labelled, ...]:
  if not (paid := received(text)): return ()
  return labelled(paid, spoken("labelling").prompt, instruction("labelling"))
