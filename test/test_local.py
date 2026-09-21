import unittest
from unittest import mock

try:
  import numpy as np
  from it01.local import batched, filled, found, prompt, reader, room, schema, sizes, spans, wanted, windows, words
  MISSING = ""
except ImportError as e: MISSING = str(e)

TAKES = ("input_ids", "attention_mask", "tw_idx", "tw_mask", "q_idx", "q_mask")
GIVES = ("indices", "pair_logits", "valid_mask")

class Coded:
  def __init__(self, ids, tokens): self.ids, self.tokens = ids, tokens

class Fake:
  def encode(self, text, add_special_tokens=False):
    head, tail = text.split("[SEP_TEXT] ")
    said = tail.split()
    return Coded([9] * head.count("[E]") + [2] + [3] * len(said), ["[E]"] * head.count("[E]") + ["[SEP_TEXT]"] + ["▁" + w for w in said])
  def token_to_id(self, name): return {"[SEP_TEXT]": 2, "[E]": 9}.get(name, 1)

class Halved(Fake):
  def encode(self, text, add_special_tokens=False):
    out = super().encode(text)
    return Coded(out.ids, [t.lstrip("▁") if i == len(out.tokens) - 1 else t for i, t in enumerate(out.tokens)])

class Nameless(Fake):
  def token_to_id(self, name): return None if name == "[SEP_TEXT]" else 9

class Deaf(Fake):
  def encode(self, text, add_special_tokens=False):
    out = super().encode(text)
    return Coded([1 if x == 9 else x for x in out.ids], out.tokens)

class Size:
  def __init__(self, name, size): self.name, self.shape = name, [1, size]

class Flat:
  def __init__(self, name): self.name, self.shape = name, [64]

class Model:
  def __init__(self, last=6, logit=9.0, takes=TAKES, gives=GIVES, size=64, dims=4, first=1, cap=None, each=None):
    self.last, self.logit, self.takes, self.gives, self.size, self.dims = last, logit, takes, gives, size, dims
    self.first, self.cap, self.each = first, cap, list(each or [])
  def get_inputs(self): return [Size(n, self.cap if self.cap is not None and n == "input_ids" else self.size) for n in self.takes]
  def get_outputs(self): return [Size(n, 0) for n in self.gives]
  def run(self, names, feed):
    first, last = self.each.pop(0) if self.each else (self.first, self.last)
    seen = np.array([[[first, last]]]) if self.dims == 3 else np.array([[[[first, last]]]])
    return [seen, np.array([[[self.logit]]]), np.array([[[True]]])][:len(self.gives)]

def sized(model=None): return sizes(model or Model())

@unittest.skipIf(MISSING, f"the local extra is not installed: {MISSING}")
class TestLocal(unittest.TestCase):
  def test_words_are_split_the_way_the_model_was_trained(self):
    self.assertEqual([w for w, _, _ in words("Total emoluments  1,107,000.00")],
                     ["total", "emoluments", "1", ",", "107", ",", "000", ".", "00"])

  def test_each_word_keeps_where_it_came_from(self):
    text = "Tax withheld 71,401.00"
    self.assertEqual([text[s:e] for _, s, e in words(text)][:2], ["Tax", "withheld"])

  def test_the_schema_names_every_field_twice(self):
    said = schema({"salary": "the gross pay", "paye_withheld": "tax already taken off"})
    for name in ("salary", "paye_withheld"):
      self.assertEqual(said.count(name), 2, name)
    self.assertEqual(said.count("[E]"), 2)

  def test_fields_are_asked_in_groups_the_model_can_hold(self):
    held = {f"f{n}": "a thing" for n in range(7)}
    self.assertEqual([list(part) for part in batched(held, 3)], [["f0", "f1", "f2"], ["f3", "f4", "f5"], ["f6"]])

  def test_a_short_input_is_padded_and_marked(self):
    values, kept = filled([4, 5], 5, "words")
    self.assertEqual(values.tolist(), [[4, 5, 0, 0, 0]])
    self.assertEqual(kept.tolist(), [[True, True, False, False, False]])

  def test_a_document_too_big_for_the_model_is_refused(self):
    with self.assertRaisesRegex(ValueError, "the model file takes 2"): filled([1, 2, 3], 2, "words")

  def test_a_model_file_of_no_fixed_size_is_refused(self):
    loose = Model()
    loose.get_inputs = lambda: [Size(n, "batch" if n == "input_ids" else 64) for n in TAKES]
    with self.assertRaisesRegex(ValueError, "leaves input_ids unsized"): sizes(loose)

  def test_a_model_file_that_wants_other_inputs_is_refused(self):
    with self.assertRaisesRegex(ValueError, "this gives \\['input_ids'"): sizes(Model(takes=TAKES + ("extra",)))

  def test_a_model_file_that_takes_an_input_of_one_dimension_is_refused(self):
    loose = Model()
    loose.get_inputs = lambda: [Size(n, 64) if n != "q_idx" else Flat(n) for n in TAKES]
    with self.assertRaisesRegex(ValueError, "q_idx in 1 dimensions"): sizes(loose)

  def test_a_model_file_that_answers_with_other_names_is_refused(self):
    with self.assertRaisesRegex(ValueError, "\\['valid_mask'\\]"):
      spans(Model(gives=GIVES[:-1]), Fake(), words("a b"), {"salary": "pay"}, sized())

  def test_a_model_file_that_answers_in_other_shapes_is_refused(self):
    with self.assertRaisesRegex(ValueError, "indices in 3 dimensions"):
      spans(Model(dims=3), Fake(), words("a b"), {"salary": "pay"}, sized())

  def test_reading_with_no_model_file_named_is_refused(self):
    with mock.patch("it01.local.IT01_MODEL_FILE", ""):
      with self.assertRaisesRegex(ValueError, "set IT01_MODEL_FILE"): reader()

  def test_reading_with_a_model_file_that_is_not_there_is_refused(self):
    with mock.patch("it01.local.IT01_MODEL_FILE", "/no/such/reader.onnx"):
      with self.assertRaisesRegex(ValueError, "which is not a file"): reader()

  def test_a_tokeniser_that_splits_the_words_differently_is_refused(self):
    with self.assertRaisesRegex(ValueError, "cannot be traced"): prompt(Halved(), words("a b c"), {"salary": "pay"})

  def test_a_tokeniser_that_does_not_know_the_marks_is_refused(self):
    with self.assertRaisesRegex(ValueError, "no \\[SEP_TEXT\\]"): prompt(Nameless(), words("a b"), {"salary": "pay"})

  def test_a_tokeniser_that_marks_no_field_is_refused(self):
    with self.assertRaisesRegex(ValueError, "marked 0 of 1 fields"): prompt(Deaf(), words("a b"), {"salary": "pay"})

  def test_a_span_names_the_words_it_covers(self):
    self.assertEqual(spans(Model(), Fake(), words("pay 1,200.00"), {"salary": "pay"}, sized()), {"salary": [(100, 1, 6)]})

  def test_a_span_below_the_confidence_is_left_out(self):
    self.assertEqual(spans(Model(logit=-1.0), Fake(), words("pay 1,200.00"), {"salary": "pay"}, sized()), {"salary": []})

  def test_a_span_reaching_past_the_document_is_left_out(self):
    self.assertEqual(spans(Model(last=9), Fake(), words("a b"), {"salary": "pay"}, sized()), {"salary": []})

  def test_a_confidence_below_what_a_number_holds_is_still_read(self):
    self.assertEqual(spans(Model(logit=-1e4), Fake(), words("pay 1,200.00"), {"salary": "pay"}, sized()), {"salary": []})

  def test_a_document_is_read_into_facts(self):
    with mock.patch("it01.local.reader", lambda: (Model(), Fake())), mock.patch("it01.local.data", lambda name: {"fields": {"salary": "pay"}}):
      self.assertEqual([(f.fact, str(f.amt), f.sure) for f in found("pay 1,200.00")], [("salary", "1200.00", 100)])

  def test_a_span_that_holds_no_figure_is_left_out(self):
    with mock.patch("it01.local.reader", lambda: (Model(last=2), Fake())), mock.patch("it01.local.data", lambda name: {"fields": {"salary": "pay"}}):
      self.assertEqual(found("pay emoluments"), ())

  def test_a_document_that_fits_is_read_in_one_window(self):
    self.assertEqual(windows(Fake(), words("a b c"), {"salary": "pay"}, {"input_ids": 64, "tw_idx": 64}), [(0, 3)])

  def test_a_document_too_long_is_read_in_overlapping_windows(self):
    self.assertEqual(windows(Fake(), words("a b c d e f"), {"salary": "pay"}, {"input_ids": 6, "tw_idx": 64}), [(0, 3), (2, 3), (4, 2)])

  def test_a_window_never_holds_more_words_than_the_model_takes(self):
    self.assertEqual(windows(Fake(), words("a b c d e f"), {"salary": "pay"}, {"input_ids": 64, "tw_idx": 2}),
                     [(0, 2), (1, 2), (2, 2), (3, 2), (4, 2)])

  def test_field_descriptions_leaving_no_room_are_refused(self):
    with self.assertRaisesRegex(ValueError, "leave no room for the document"): room(Fake(), words("a b"), {"salary": "pay"}, 2)

  def test_the_same_words_seen_from_two_windows_are_reported_once(self):
    with mock.patch("it01.local.reader", lambda: (Model(cap=15, each=[(10, 11), (1, 2)]), Fake())), \
         mock.patch("it01.local.data", lambda name: {"fields": {"salary": "pay"}}):
      self.assertEqual([(f.fact, str(f.amt)) for f in found(" ".join(str(n % 10) for n in range(15)))], [("salary", "0")])

  def test_the_same_figure_in_two_places_is_reported_twice(self):
    with mock.patch("it01.local.reader", lambda: (Model(cap=15, each=[(1, 2), (1, 2)]), Fake())), \
         mock.patch("it01.local.data", lambda name: {"fields": {"salary": "pay"}}):
      self.assertEqual([str(f.amt) for f in found(" ".join(["1"] * 15))], ["1", "1"])

  def test_a_span_cut_by_the_start_of_a_window_is_left_out(self):
    with mock.patch("it01.local.reader", lambda: (Model(cap=15, each=[(1, 2), (0, 1)]), Fake())), \
         mock.patch("it01.local.data", lambda name: {"fields": {"salary": "pay"}}):
      self.assertEqual([str(f.amt) for f in found(" ".join(["1"] * 15))], ["1"])

  def test_a_span_on_the_first_word_of_the_document_is_kept(self):
    with mock.patch("it01.local.reader", lambda: (Model(cap=15, each=[(0, 1), (5, 6)]), Fake())), \
         mock.patch("it01.local.data", lambda name: {"fields": {"salary": "pay"}}):
      self.assertEqual([str(f.amt) for f in found(" ".join(["1"] * 15))], ["1", "1"])

  def test_a_span_on_the_last_word_of_the_document_is_kept(self):
    with mock.patch("it01.local.reader", lambda: (Model(cap=15, each=[(1, 2), (5, 6)]), Fake())), \
         mock.patch("it01.local.data", lambda name: {"fields": {"salary": "pay"}}):
      self.assertEqual([str(f.amt) for f in found(" ".join(["1"] * 15))], ["1", "1"])

  def test_a_span_cut_by_the_end_of_a_window_is_left_out(self):
    with mock.patch("it01.local.reader", lambda: (Model(cap=15, each=[(11, 12), (1, 2)]), Fake())), \
         mock.patch("it01.local.data", lambda name: {"fields": {"salary": "pay"}}):
      self.assertEqual([str(f.amt) for f in found(" ".join(["1"] * 15))], ["1"])

  def test_a_document_with_no_words_is_refused(self):
    with self.assertRaisesRegex(ValueError, "holds no words"): found("   ")

  def test_fields_the_package_does_not_know_are_refused(self):
    with mock.patch("it01.local.data", lambda name: {"fields": {"bonus_points": "a thing"}}):
      with self.assertRaisesRegex(ValueError, "does not know \\['bonus_points'\\]"): wanted()

  def test_fields_that_carry_no_description_are_refused(self):
    with mock.patch("it01.local.data", lambda name: {"fields": {"salary": ""}}):
      with self.assertRaisesRegex(ValueError, "an object of descriptions"): wanted()

if __name__ == "__main__": unittest.main()
