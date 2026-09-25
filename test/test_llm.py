import io, json, unittest
from unittest import mock
from it01.llm import ask

def sent(*given:object) -> dict[str, object]:
  answer = io.BytesIO(json.dumps({"choices": [{"message": {"content": "{}"}}]}).encode())
  with mock.patch("urllib.request.urlopen", return_value=answer) as opened: ask("label these", "1. salary", *given)
  return json.loads(opened.call_args.args[0].data)

class TestAsk(unittest.TestCase):
  def test_a_schema_goes_to_the_endpoint_as_the_answer_format(self):
    schema = {"type": "object", "properties": {"1": {"type": "string"}}, "required": ["1"], "additionalProperties": False}
    self.assertEqual(sent(schema)["response_format"], {"type": "json_schema", "json_schema": {"name": "answer", "strict": True, "schema": schema}})

  def test_without_a_schema_no_answer_format_is_asked_for(self):
    self.assertNotIn("response_format", sent())

if __name__ == "__main__": unittest.main()
