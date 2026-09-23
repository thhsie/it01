import json, os, pathlib, tempfile, unittest
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

if __name__ == "__main__": unittest.main()
