import json, urllib.error, urllib.request
from decimal import Decimal
from it01.helpers import IT01_DEBUG, IT01_ENDPOINT, IT01_KEY, IT01_MODEL, IT01_TIMEOUT

def ask(instruction:str, document:str) -> str:
  body = json.dumps({"model": IT01_MODEL, "temperature": 0,
                     "messages": [{"role": "system", "content": instruction}, {"role": "user", "content": document}]}).encode()
  headers = {"Content-Type": "application/json"} | ({"Authorization": f"Bearer {IT01_KEY}"} if IT01_KEY else {})
  request = urllib.request.Request(IT01_ENDPOINT, body, headers)
  try:
    with urllib.request.urlopen(request, timeout=IT01_TIMEOUT) as resp: answer = resp.read().decode(errors="replace")
  except urllib.error.HTTPError as e: raise ValueError(f"the model endpoint {IT01_ENDPOINT} answered {e.code} {e.reason}") from e
  except (TimeoutError, urllib.error.URLError) as e: raise OSError(f"cannot reach the model endpoint {IT01_ENDPOINT}") from e
  if IT01_DEBUG >= 2: print(answer)
  try: reply = json.loads(answer, parse_float=Decimal)
  except json.JSONDecodeError: raise ValueError(f"the endpoint did not answer with JSON {answer}") from None
  if not isinstance(reply, dict) or not isinstance(choices := reply.get("choices"), list) or not choices:
    raise ValueError(f"the endpoint answered without choices {reply}")
  first = choices[0]
  inner = first.get("message") if isinstance(first, dict) else None
  content = inner.get("content") if isinstance(inner, dict) else None
  if not isinstance(content, str): raise ValueError(f"the endpoint answered without a message {first}")
  return content
