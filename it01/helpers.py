import json, os, pathlib
from typing import Any

def flag(name:str, default:str) -> str: return os.environ.get(name, default)

def number(name:str, default:str) -> int:
  if not (value := flag(name, default)).isdecimal(): raise ValueError(f"{name} must be a whole number, not {value}")
  return int(value)

def folder(name:str, default:str) -> str:
  if (value := flag(name, default)) and not pathlib.Path(value).is_dir(): raise ValueError(f"{name} must be a folder, not {value}")
  return value

IT01_ENDPOINT = flag("IT01_ENDPOINT", "http://localhost:8080/v1/chat/completions")
IT01_MODEL = flag("IT01_MODEL", "local")
IT01_KEY = flag("IT01_KEY", "")
IT01_DEBUG = number("IT01_DEBUG", "0")
IT01_TIMEOUT = number("IT01_TIMEOUT", "120")
IT01_MODEL_FILE = flag("IT01_MODEL_FILE", "")
IT01_TOKENISER = flag("IT01_TOKENISER", "")
IT01_DATA = folder("IT01_DATA", "")

def data(name:str) -> dict[str, Any]:
  shipped = pathlib.Path(__file__).parent / f"{name}.json"
  own = pathlib.Path(IT01_DATA) / f"{name}.json" if IT01_DATA else shipped
  raw = json.loads((own if own.exists() else shipped).read_text())
  if not isinstance(raw, dict): raise ValueError(f"{name}.json must hold a JSON object")
  return raw

def instruction(name:str) -> str:
  if not isinstance(text := data(name).get("instruction"), str): raise ValueError(f"{name}.json must hold an instruction string, not {text}")
  return text
