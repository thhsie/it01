import json, pathlib, tempfile, unittest
from unittest import mock
from it01.__main__ import opened, source
from it01.keep import fingerprint

try:
  from it01 import local
  from it01.paper import pictured
  MISSING = ""
except ImportError as e: MISSING = str(e)

LINES = (b"Total emoluments  1,107,000.00", b"Tax withheld  71,401.00")

def page(said:tuple[bytes, ...], n:int) -> list[bytes]:
  body = b"\n".join(b"BT /F1 12 Tf 72 %d Td (%s) Tj ET" % (720 - 20 * i, line) for i, line in enumerate(said))
  return [b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>" % (n + 1, n),
          b"<< /Length %d >>\nstream\n" % len(body) + body + b"\nendstream"]

def written(*sheets:tuple[bytes, ...]) -> bytes:
  kids = b" ".join(b"%d 0 R" % (3 + 3 * n) for n in range(len(sheets)))
  objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, len(sheets))]
  for n, said in enumerate(sheets):
    objs += page(said, 4 + 3 * n) + [b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
  ret, offsets = b"%PDF-1.4\n", []
  for n, obj in enumerate(objs, 1):
    offsets.append(len(ret))
    ret += b"%d 0 obj\n" % n + obj + b"\nendobj\n"
  start = len(ret)
  ret += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % off for off in offsets)
  return ret + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, start)

def saved(raw:bytes, suffix:str) -> pathlib.Path:
  with tempfile.NamedTemporaryFile("wb", suffix=suffix, delete=False) as f: f.write(raw)
  return pathlib.Path(f.name)

class TestPaper(unittest.TestCase):
  def test_a_file_that_is_not_a_pdf_is_read_as_text(self):
    here = saved(b"Total emoluments  1,107,000.00\n", ".txt")
    self.addCleanup(here.unlink)
    self.assertEqual(source(here), "Total emoluments  1,107,000.00\n")

  def test_a_file_read_differently_since_is_still_shown(self):
    here = saved(b"Total emoluments  1,107,000.00\n", ".txt")
    self.addCleanup(here.unlink)
    facts = {"resident": True, "paths": {here.name: str(here)}, "texts": {fingerprint(here.read_bytes()): here.name}}
    held_at = saved(json.dumps(facts).encode(), ".json")
    self.addCleanup(held_at.unlink)
    with mock.patch("it01.__main__.source", return_value="Total emoluments  1,107,000.60"):
      self.assertEqual(opened(held_at, here.name), ["Total emoluments  1,107,000.60"])

def told(*pages:str): return mock.patch.object(local, "looked", lambda shots: pages[:len(shots)])

@unittest.skipIf(MISSING, f"the pdf and local extras are not installed: {MISSING}")
class TestPdf(unittest.TestCase):
  def test_each_page_is_a_picture_of_the_page(self):
    here = saved(written(LINES[:1], LINES[1:]), ".pdf")
    self.addCleanup(here.unlink)
    self.assertEqual([shot[1:3] for shot in pictured(here)], [(1224, 1584), (1224, 1584)])

  def test_the_picture_shows_the_writing(self):
    here = saved(written(LINES), ".pdf")
    self.addCleanup(here.unlink)
    self.assertLess(min(pictured(here)[0][0]), 128)

  def test_each_page_is_read_off_its_picture(self):
    here = saved(written(LINES[:1], LINES[1:]), ".pdf")
    self.addCleanup(here.unlink)
    with told("one", "two"): self.assertEqual(source(here), "one\n\ftwo")

  def test_a_page_with_nothing_read_is_refused(self):
    here = saved(written(LINES, LINES), ".pdf")
    self.addCleanup(here.unlink)
    with told("Tax  9.00", " "), self.assertRaisesRegex(ValueError, "nothing could be read on .* page 2"): source(here)

  def test_a_pdf_a_case_read_is_shown_line_by_line(self):
    here = saved(written(LINES), ".pdf")
    self.addCleanup(here.unlink)
    facts = {"resident": True, "paths": {here.name: str(here)}, "texts": {fingerprint(here.read_bytes()): here.name}}
    held_at = saved(json.dumps(facts).encode(), ".json")
    self.addCleanup(held_at.unlink)
    with told("\n".join(line.decode() for line in LINES)):
      self.assertEqual(opened(held_at, here.name), [line.decode() for line in LINES])

  def test_a_pdf_is_read_by_its_suffix(self):
    for suffix in (".pdf", ".PDF"):
      with self.subTest(suffix), told("Total emoluments  1,107,000.00"):
        here = saved(written(LINES), suffix)
        self.addCleanup(here.unlink)
        self.assertEqual(source(here), "Total emoluments  1,107,000.00")

  def test_a_file_that_does_not_read_as_a_pdf_is_refused(self):
    here = saved(b"not a pdf at all", ".pdf")
    self.addCleanup(here.unlink)
    with self.assertRaisesRegex(ValueError, "does not read as a PDF"): source(here)

if __name__ == "__main__": unittest.main()
