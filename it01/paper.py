import pathlib
import pypdfium2

SCALE = 2

def pictured(here:pathlib.Path) -> tuple[tuple[bytes, int, int, int], ...]:
  try: held = pypdfium2.PdfDocument(here)
  except pypdfium2.PdfiumError as e: raise ValueError(f"{here.name} does not read as a PDF ({e})") from e
  with held:
    shots = [page.render(scale=SCALE, rev_byteorder=True, force_bitmap_format=pypdfium2.raw.FPDFBitmap_BGR) for page in held]
    return tuple((bytes(shot.buffer), shot.width, shot.height, shot.stride) for shot in shots)
