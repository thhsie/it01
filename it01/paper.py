import pathlib
from pypdf import PdfReader
from pypdf.errors import PyPdfError

def to_text(here:pathlib.Path) -> str:
  try: pages = [page.extract_text(extraction_mode="layout") for page in PdfReader(here).pages]
  except PyPdfError as e: raise ValueError(f"{here.name} does not read as a PDF ({e})") from e
  if bare := [str(n) for n, page in enumerate(pages, 1) if not page.strip()]:
    raise ValueError(f"no text on {here.name} page {', '.join(bare)}, so it has to be read off the page first")
  return "\n\f".join(pages)
