import json, os, pathlib, subprocess, sys, tempfile, unittest
from unittest import mock
from it01.helpers import data, folder

class TestData(unittest.TestCase):
  def test_the_shipped_file_is_used_by_default(self):
    self.assertIn("kinds", data("labelling"))

  def test_a_file_of_your_own_is_used_instead(self):
    with tempfile.TemporaryDirectory() as mine:
      (pathlib.Path(mine)/"labelling.json").write_text(json.dumps({"kinds": {"gift": "a gift"}}))
      with mock.patch("it01.helpers.IT01_DATA", mine): self.assertEqual(data("labelling")["kinds"], {"gift": "a gift"})

  def test_a_name_not_in_the_folder_comes_from_the_package(self):
    with tempfile.TemporaryDirectory() as mine:
      with mock.patch("it01.helpers.IT01_DATA", mine): self.assertIn("kinds", data("labelling"))

  def test_a_folder_that_is_not_there_is_refused(self):
    with mock.patch.dict(os.environ, {"IT01_DATA": "/no/such/place"}):
      with self.assertRaisesRegex(ValueError, "IT01_DATA must be a folder, not /no/such/place"): folder("IT01_DATA", "")

  def test_no_folder_is_no_trouble(self):
    with mock.patch.dict(os.environ, {}, clear=True): self.assertEqual(folder("IT01_DATA", ""), "")

  def test_a_file_that_is_not_an_object_is_refused(self):
    with tempfile.TemporaryDirectory() as mine:
      (pathlib.Path(mine)/"labelling.json").write_text("[]")
      with mock.patch("it01.helpers.IT01_DATA", mine):
        with self.assertRaisesRegex(ValueError, "labelling.json must hold a JSON object"): data("labelling")

  def test_utf8_whatever_the_locale(self):
    plain = {**os.environ, "LC_ALL": "C", "PYTHONCOERCECLOCALE": "0", "PYTHONUTF8": "0"}
    code = "\n".join(["import pathlib, sys", "from it01.helpers import data", "from it01.__main__ import held_in, rewritten", "data('model')",
                      "here = pathlib.Path(sys.argv[1])", "rewritten(here, held_in(here))",
                      "sys.stdout.buffer.write(held_in(here).sources['salary'].encode('utf-8'))"])
    with tempfile.TemporaryDirectory() as mine:
      (pathlib.Path(mine)/"case.json").write_bytes('{"resident": true, "salary": 1, "sources": {"salary": "Emile \u00e9"}}'.encode())
      here = str(pathlib.Path(mine)/"case.json")
      root = pathlib.Path(__file__).parent.parent
      ran = subprocess.run([sys.executable, "-c", code, here], cwd=root, env=plain, capture_output=True, encoding="utf-8")
    self.assertEqual((ran.returncode, ran.stdout.strip()), (0, "Emile \u00e9"), ran.stderr)

if __name__ == "__main__": unittest.main()
