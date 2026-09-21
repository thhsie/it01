import unittest
from decimal import Decimal
from unittest import mock

try:
  import numpy as np
  from it01.local import Form, Found, Working, batched, filled, found, prompt, reader, room
  from it01.local import shaped, sizes, spans, sums, wanted, windows, words, written
  FORM = Form("statement_of_emoluments", (("salary", "the gross pay"),))
  SHAPE = shaped()
  SCHEMA = SHAPE.schema
  HELD = {"form": {"name": FORM.name, "fields": dict(FORM.fields)}}
  SHOWN = {"takes": dict(zip(("tokens", "attention", "words", "word_mask", "lines", "line_mask"), SHAPE.takes)),
           "gives": dict(zip(("spans", "scores", "valid"), SHAPE.gives)),
           "schema": {"form": SCHEMA.form, "describes": SCHEMA.describes, "lists": SCHEMA.lists, "document": SCHEMA.document},
           "line_mark": SHAPE.line_mark, "text_mark": SHAPE.text_mark, "word_start": SHAPE.word_start}
  MISSING = ""
except ImportError as e: MISSING = str(e)

class Coded:
  def __init__(self, ids, tokens): self.ids, self.tokens = ids, tokens

class Fake:
  def encode(self, text, add_special_tokens=False):
    head, tail = text.split(SHAPE.text_mark + " ")
    said = tail.split()
    marked = head.count(SHAPE.line_mark)
    return Coded([9] * marked + [2] + [3] * len(said),
                 [SHAPE.line_mark] * marked + [SHAPE.text_mark] + [SHAPE.word_start + w for w in said])
  def token_to_id(self, name): return {SHAPE.text_mark: 2, SHAPE.line_mark: 9}.get(name, 1)

class Halved(Fake):
  def encode(self, text, add_special_tokens=False):
    out = super().encode(text)
    return Coded(out.ids, [t.lstrip("▁") if i == len(out.tokens) - 1 else t for i, t in enumerate(out.tokens)])

class Nameless(Fake):
  def token_to_id(self, name): return None if name == SHAPE.text_mark else 9

class Deaf(Fake):
  def encode(self, text, add_special_tokens=False):
    out = super().encode(text)
    return Coded([1 if x == 9 else x for x in out.ids], out.tokens)

class Size:
  def __init__(self, name, size): self.name, self.shape = name, [1, size]

class Flat:
  def __init__(self, name): self.name, self.shape = name, [64]

class Model:
  def __init__(self, last=6, logit=9.0, takes=None, gives=None, size=64, dims=4, first=1, cap=None, each=None):
    self.last, self.logit, self.size, self.dims, self.first, self.cap = last, logit, size, dims, first, cap
    self.takes, self.gives, self.each = takes or SHAPE.takes, gives or SHAPE.gives, list(each or [])
  def get_inputs(self): return [Size(n, self.cap if self.cap is not None and n == "tokens" else self.size) for n in self.takes]
  def get_outputs(self): return [Size(n, 0) for n in self.gives]
  def run(self, names, feed):
    first, last = self.each.pop(0) if self.each else (self.first, self.last)
    seen = np.array([[[first, last]]]) if self.dims == 3 else np.array([[[[first, last]]]])
    return [seen, np.array([[[self.logit]]]), np.array([[[True]]])][:len(self.gives)]

def sized(model=None): return sizes(model or Model(), SHAPE)

@unittest.skipIf(MISSING, f"the local extra is not installed: {MISSING}")
class TestLocal(unittest.TestCase):
  def test_words_are_split_the_way_the_model_was_trained(self):
    self.assertEqual([w for w, _, _ in words("Total emoluments  1,107,000.00")],
                     ["total", "emoluments", "1", ",", "107", ",", "000", ".", "00"])

  def test_each_word_keeps_where_it_came_from(self):
    text = "Tax withheld 71,401.00"
    self.assertEqual([text[s:e] for _, s, e in words(text)][:2], ["Tax", "withheld"])

  def test_the_input_names_the_form_and_every_line_twice(self):
    form = Form("statement_of_emoluments", (("salary", "the gross pay"), ("tax_withheld", "tax already taken off")))
    said = written(SHAPE, form, words("a b"))
    self.assertIn("statement_of_emoluments", said)
    for name in ("salary", "tax_withheld"):
      self.assertEqual(said.count(name), 2, name)
    self.assertEqual(said.count(SHAPE.line_mark), 2)

  def test_the_document_follows_the_mark_that_starts_it(self):
    self.assertIn(SHAPE.text_mark + " pay 12", written(SHAPE, FORM, words("pay 12")))

  def test_lines_are_asked_in_groups_the_model_can_hold(self):
    parts = batched(Form("soe", tuple((f"f{n}", "a thing") for n in range(7))), 3)
    self.assertEqual([[n for n, _ in part.fields] for part in parts], [["f0", "f1", "f2"], ["f3", "f4", "f5"], ["f6"]])
    self.assertEqual({part.name for part in parts}, {"soe"})

  def test_a_short_input_is_padded_and_marked(self):
    values, kept = filled([4, 5], 5, "words")
    self.assertEqual(values.tolist(), [[4, 5, 0, 0, 0]])
    self.assertEqual(kept.tolist(), [[True, True, False, False, False]])

  def test_a_document_too_big_for_the_model_is_refused(self):
    with self.assertRaisesRegex(ValueError, "the model file takes 2"): filled([1, 2, 3], 2, "words")

  def test_a_model_file_of_no_fixed_size_is_refused(self):
    loose = Model()
    loose.get_inputs = lambda: [Size(n, "batch" if n == "tokens" else 64) for n in SHAPE.takes]
    with self.assertRaisesRegex(ValueError, "leaves tokens unsized"): sizes(loose, SHAPE)

  def test_a_model_file_that_wants_other_inputs_is_refused(self):
    with self.assertRaisesRegex(ValueError, "model.json names"): sizes(Model(takes=SHAPE.takes + ("extra",)), SHAPE)

  def test_a_model_file_that_takes_an_input_of_one_dimension_is_refused(self):
    loose = Model()
    loose.get_inputs = lambda: [Size(n, 64) if n != "lines" else Flat(n) for n in SHAPE.takes]
    with self.assertRaisesRegex(ValueError, "lines in 1 dimensions"): sizes(loose, SHAPE)

  def test_a_model_file_that_answers_with_other_names_is_refused(self):
    with self.assertRaisesRegex(ValueError, "\\['valid'\\]"):
      spans(Model(gives=SHAPE.gives[:-1]), Fake(), words("a b"), FORM, SHAPE, sized())

  def test_a_model_file_that_answers_in_other_shapes_is_refused(self):
    with self.assertRaisesRegex(ValueError, "spans in 3 dimensions"):
      spans(Model(dims=3), Fake(), words("a b"), FORM, SHAPE, sized())

  def test_reading_with_no_model_file_named_is_refused(self):
    with mock.patch("it01.local.IT01_MODEL_FILE", ""):
      with self.assertRaisesRegex(ValueError, "set IT01_MODEL_FILE"): reader()

  def test_reading_with_a_model_file_that_is_not_there_is_refused(self):
    with mock.patch("it01.local.IT01_MODEL_FILE", "/no/such/reader.onnx"):
      with self.assertRaisesRegex(ValueError, "which is not a file"): reader()

  def test_a_tokeniser_that_splits_the_words_differently_is_refused(self):
    with self.assertRaisesRegex(ValueError, "cannot be traced"): prompt(Halved(), words("a b c"), FORM, SHAPE)

  def test_a_tokeniser_that_does_not_know_the_marks_is_refused(self):
    with self.assertRaisesRegex(ValueError, "the tokeniser has no"): prompt(Nameless(), words("a b"), FORM, SHAPE)

  def test_a_tokeniser_that_marks_no_line_is_refused(self):
    with self.assertRaisesRegex(ValueError, "marked 0 of 1 lines"): prompt(Deaf(), words("a b"), FORM, SHAPE)

  def test_a_span_names_the_words_it_covers(self):
    self.assertEqual(spans(Model(), Fake(), words("pay 1,200.00"), FORM, SHAPE, sized()), {"salary": [(100, 1, 6)]})

  def test_a_span_below_the_confidence_is_left_out(self):
    self.assertEqual(spans(Model(logit=-1.0), Fake(), words("pay 1,200.00"), FORM, SHAPE, sized()), {"salary": []})

  def test_a_confidence_below_what_a_number_holds_is_still_read(self):
    self.assertEqual(spans(Model(logit=-1e4), Fake(), words("pay 1,200.00"), FORM, SHAPE, sized()), {"salary": []})

  def test_a_span_reaching_past_the_document_is_left_out(self):
    self.assertEqual(spans(Model(last=9), Fake(), words("a b"), FORM, SHAPE, sized()), {"salary": []})

  def test_a_document_that_fits_is_read_in_one_window(self):
    self.assertEqual(windows(Fake(), words("a b c"), FORM, SHAPE, {"tokens": 64, "words": 64}), [(0, 3)])

  def test_a_document_too_long_is_read_in_overlapping_windows(self):
    self.assertEqual(windows(Fake(), words("a b c d e f"), FORM, SHAPE, {"tokens": 6, "words": 64}), [(0, 3), (2, 3), (4, 2)])

  def test_a_window_never_holds_more_words_than_the_model_takes(self):
    self.assertEqual(windows(Fake(), words("a b c d e f"), FORM, SHAPE, {"tokens": 64, "words": 2}),
                     [(0, 2), (1, 2), (2, 2), (3, 2), (4, 2)])

  def test_a_form_leaving_no_room_is_refused(self):
    with self.assertRaisesRegex(ValueError, "leaves no room for the document"): room(Fake(), words("a b"), FORM, SHAPE, 2)

  def test_the_same_words_seen_from_two_windows_are_reported_once(self):
    with mock.patch("it01.local.reader", lambda: (Model(cap=15, each=[(10, 11), (1, 2)]), Fake())), \
         mock.patch("it01.local.data", lambda name: HELD if name == "reading" else SHOWN):
      self.assertEqual([(f.field, str(f.amt)) for f in found(" ".join(str(n % 10) for n in range(15)))], [("salary", "0")])

  def test_the_same_figure_in_two_places_is_reported_twice(self):
    with mock.patch("it01.local.reader", lambda: (Model(cap=15, each=[(1, 2), (1, 2)]), Fake())), \
         mock.patch("it01.local.data", lambda name: HELD if name == "reading" else SHOWN):
      self.assertEqual([str(f.amt) for f in found(" ".join(["1"] * 15))], ["1", "1"])

  def test_a_span_cut_by_the_start_of_a_window_is_left_out(self):
    with mock.patch("it01.local.reader", lambda: (Model(cap=15, each=[(1, 2), (0, 1)]), Fake())), \
         mock.patch("it01.local.data", lambda name: HELD if name == "reading" else SHOWN):
      self.assertEqual([str(f.amt) for f in found(" ".join(["1"] * 15))], ["1"])

  def test_a_span_on_the_first_word_of_the_document_is_kept(self):
    with mock.patch("it01.local.reader", lambda: (Model(cap=15, each=[(0, 1), (5, 6)]), Fake())), \
         mock.patch("it01.local.data", lambda name: HELD if name == "reading" else SHOWN):
      self.assertEqual([str(f.amt) for f in found(" ".join(["1"] * 15))], ["1", "1"])

  def test_a_span_on_the_last_word_of_the_document_is_kept(self):
    with mock.patch("it01.local.reader", lambda: (Model(cap=15, each=[(1, 2), (5, 6)]), Fake())), \
         mock.patch("it01.local.data", lambda name: HELD if name == "reading" else SHOWN):
      self.assertEqual([str(f.amt) for f in found(" ".join(["1"] * 15))], ["1", "1"])

  def test_a_span_cut_by_the_end_of_a_window_is_left_out(self):
    with mock.patch("it01.local.reader", lambda: (Model(cap=15, each=[(11, 12), (1, 2)]), Fake())), \
         mock.patch("it01.local.data", lambda name: HELD if name == "reading" else SHOWN):
      self.assertEqual([str(f.amt) for f in found(" ".join(["1"] * 15))], ["1"])

  def test_a_document_is_read_into_facts(self):
    with mock.patch("it01.local.reader", lambda: (Model(), Fake())), \
         mock.patch("it01.local.data", lambda name: HELD if name == "reading" else SHOWN):
      self.assertEqual([(f.field, str(f.amt), f.sure) for f in found("pay 1,200.00")], [("salary", "1200.00", 100)])

  def test_a_span_that_holds_no_figure_is_left_out(self):
    with mock.patch("it01.local.reader", lambda: (Model(last=2), Fake())), \
         mock.patch("it01.local.data", lambda name: HELD if name == "reading" else SHOWN):
      self.assertEqual(found("pay emoluments"), ())

  def test_a_document_with_no_words_is_refused(self):
    with self.assertRaisesRegex(ValueError, "holds no words"): found("   ")

  def test_the_form_the_package_ships_is_read(self):
    shipped = wanted()
    self.assertTrue(shipped.name)
    self.assertTrue(shipped.fields)

  def test_the_shape_the_package_ships_writes_the_form_it_ships(self):
    shipped, form = shaped(), wanted()
    said = written(shipped, form, words("pay 12"))
    self.assertIn(form.name, said)
    self.assertIn(form.fields[0][0], said)
    self.assertIn(shipped.line_mark, said)

  def test_a_form_with_no_name_is_refused(self):
    with mock.patch("it01.local.data", lambda name: {"form": {"fields": {"salary": "pay"}}}):
      with self.assertRaisesRegex(ValueError, "must hold name"): wanted()

  def test_lines_that_carry_no_description_are_refused(self):
    with mock.patch("it01.local.data", lambda name: {"form": {"name": "soe", "fields": {"salary": ""}}}):
      with self.assertRaisesRegex(ValueError, "an object of descriptions"): wanted()

  def test_a_feed_naming_a_line_the_form_does_not_have_is_refused(self):
    with mock.patch("it01.local.data", lambda name: {"form": {"name": "soe", "fields": {"salary": "pay"}, "feeds": {"wages": "salary"}}}):
      with self.assertRaisesRegex(ValueError, "feeds lines the form does not have"): wanted()

  def test_a_feed_naming_a_fact_the_package_does_not_know_is_refused(self):
    with mock.patch("it01.local.data", lambda name: {"form": {"name": "soe", "fields": {"salary": "pay"}, "feeds": {"salary": "wages"}}}):
      with self.assertRaisesRegex(ValueError, "feeds facts the package does not know"): wanted()

  def test_a_proposal_names_the_fact_its_line_feeds(self):
    fed = {"form": {"name": FORM.name, "fields": dict(FORM.fields), "feeds": {"salary": "salary"}}}
    with mock.patch("it01.local.reader", lambda: (Model(), Fake())), \
         mock.patch("it01.local.data", lambda name: fed if name == "reading" else SHOWN):
      self.assertEqual([(f.field, f.fact) for f in found("pay 1,200.00")], [("salary", "salary")])

  def test_a_proposal_whose_line_feeds_nothing_names_nothing(self):
    with mock.patch("it01.local.reader", lambda: (Model(), Fake())), \
         mock.patch("it01.local.data", lambda name: HELD if name == "reading" else SHOWN):
      self.assertEqual([f.fact for f in found("pay 1,200.00")], [""])

  def test_a_sum_says_whether_the_figures_come_out(self):
    form = Form("soe", (("total", "a"), ("exempt_income", "b"), ("net_emoluments", "c")), (),
                (Working("net_emoluments", ("total",), ("exempt_income",)),))
    for net, agrees in ((Decimal("1107000"), True), (Decimal("1107000.00"), True), (Decimal("1207000"), False)):
      seen = (Found("total", Decimal("1227000.00"), "", 100, ""), Found("exempt_income", Decimal("120000"), "", 100, ""),
              Found("net_emoluments", net, "", 100, ""))
      self.assertEqual(sums(form, seen)[0].agrees, agrees, net)

  def test_a_sum_missing_a_line_is_not_checked(self):
    form = Form("soe", (("total", "a"), ("exempt_income", "b"), ("net_emoluments", "c")), (),
                (Working("net_emoluments", ("total",), ("exempt_income",)),))
    self.assertEqual(sums(form, (Found("total", Decimal("1227000"), "", 100, ""),)), ())

  def test_a_sum_uses_the_figure_the_model_was_surest_of(self):
    form = Form("soe", (("total", "a"), ("exempt_income", "b"), ("net_emoluments", "c")), (),
                (Working("net_emoluments", ("total",), ("exempt_income",)),))
    seen = (Found("total", Decimal("9"), "", 60, ""), Found("total", Decimal("1227000"), "", 100, ""),
            Found("exempt_income", Decimal("120000"), "", 100, ""), Found("net_emoluments", Decimal("1107000"), "", 100, ""))
    self.assertTrue(sums(form, seen)[0].agrees)

  def test_a_check_naming_a_line_the_form_does_not_have_is_refused(self):
    held = {"form": {"name": "soe", "fields": {"salary": "pay"}, "checks": [{"is": "salary", "plus": ["wages"]}]}}
    with mock.patch("it01.local.data", lambda name: held):
      with self.assertRaisesRegex(ValueError, "names lines the form does not have"): wanted()

  def test_a_check_that_does_not_say_which_line_it_works_out_is_refused(self):
    for one in ({"plus": ["salary"]}, {"is": 5}, {"is": "salary", "spare": []}, "salary", 5):
      with mock.patch("it01.local.data", lambda name: {"form": {"name": "soe", "fields": {"salary": "pay"}, "checks": [one]}}):
        with self.assertRaisesRegex(ValueError, "must say which line it works out"): wanted()

  def test_a_check_whose_sides_are_not_lists_of_names_is_refused(self):
    for one in ({"is": "salary", "plus": "salary"}, {"is": "salary", "plus": 5}, {"is": "salary", "less": [["salary"]]}):
      with mock.patch("it01.local.data", lambda name: {"form": {"name": "soe", "fields": {"salary": "pay"}, "checks": [one]}}):
        with self.assertRaisesRegex(ValueError, "lists of line names"): wanted()

  def test_a_check_that_works_a_line_out_from_itself_is_refused(self):
    held = {"form": {"name": "soe", "fields": {"salary": "pay"}, "checks": [{"is": "salary", "plus": ["salary"]}]}}
    with mock.patch("it01.local.data", lambda name: held):
      with self.assertRaisesRegex(ValueError, "works it out from itself"): wanted()

  def test_a_check_that_adds_and_takes_away_nothing_is_refused(self):
    with mock.patch("it01.local.data", lambda name: {"form": {"name": "soe", "fields": {"salary": "pay"}, "checks": [{"is": "salary"}]}}):
      with self.assertRaisesRegex(ValueError, "adds and takes away nothing"): wanted()

  def test_checks_that_are_not_a_list_are_refused(self):
    with mock.patch("it01.local.data", lambda name: {"form": {"name": "soe", "fields": {"salary": "pay"}, "checks": {}}}):
      with self.assertRaisesRegex(ValueError, "a list of sums"): wanted()

  def test_the_check_the_package_ships_works_the_net_line_out(self):
    self.assertEqual([(c.line, c.plus, c.less) for c in wanted().checks], [("net_emoluments", ("total",), ("exempt_income",))])

  def test_a_feed_that_is_not_a_name_is_refused(self):
    with mock.patch("it01.local.data", lambda name: {"form": {"name": "soe", "fields": {"salary": "pay"}, "feeds": {"salary": ["salary"]}}}):
      with self.assertRaisesRegex(ValueError, "an object from a line to a fact"): wanted()

  def test_two_lines_feeding_one_fact_are_refused(self):
    held = {"form": {"name": "soe", "fields": {"salary": "pay", "total": "the total"}, "feeds": {"salary": "salary", "total": "salary"}}}
    with mock.patch("it01.local.data", lambda name: held):
      with self.assertRaisesRegex(ValueError, "feeds one fact from more than one line"): wanted()

  def test_the_feeds_the_package_ships_are_the_two_lines_that_carry_a_fact(self):
    self.assertEqual(dict(wanted().feeds), {"net_emoluments": "salary", "tax_withheld": "paye_withheld"})

  def test_the_form_is_read_in_the_order_it_is_written(self):
    with mock.patch("it01.local.data", lambda name: {"form": {"name": "soe", "fields": {"total": "the total", "salary": "the pay"}}}):
      self.assertEqual(wanted(), Form("soe", (("total", "the total"), ("salary", "the pay"))))

  def test_a_shape_that_names_other_roles_is_refused(self):
    with mock.patch("it01.local.data", lambda name: SHOWN | {"takes": {"tokens": "a"}}):
      with self.assertRaisesRegex(ValueError, "must hold takes naming each of"): shaped()

  def test_a_shape_with_a_schema_missing_a_part_is_refused(self):
    with mock.patch("it01.local.data", lambda name: SHOWN | {"schema": {"form": "("}}):
      with self.assertRaisesRegex(ValueError, "must hold schema naming each of"): shaped()

  def test_wording_that_takes_something_else_is_refused(self):
    with mock.patch("it01.local.data", lambda name: SHOWN | {"schema": dict(SHOWN["schema"], describes="{oops}")}):
      with self.assertRaisesRegex(ValueError, "the describes wording in model.json takes"): shaped()

  def test_wording_that_leaves_out_a_name_is_refused(self):
    with mock.patch("it01.local.data", lambda name: SHOWN | {"schema": dict(SHOWN["schema"], document="[TEXT] .")}):
      with self.assertRaisesRegex(ValueError, "the document wording in model.json leaves out"): shaped()

  def test_a_mark_the_wording_never_writes_is_refused(self):
    with mock.patch("it01.local.data", lambda name: SHOWN | {"line_mark": "[NOPE]"}):
      with self.assertRaisesRegex(ValueError, "which the wording never writes"): shaped()

  def test_a_name_the_file_leaves_out_is_refused(self):
    with mock.patch("it01.local.data", lambda name: SHOWN | {"gives": dict(SHOWN["gives"], spans=None)}):
      with self.assertRaisesRegex(ValueError, "under gives must hold spans"): shaped()

if __name__ == "__main__": unittest.main()
