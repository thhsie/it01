import json, os, pathlib
from typing import Any

def flag(name:str, default:str) -> str: return os.environ.get(name, default)

def number(name:str, default:str) -> int:
  if not (value := flag(name, default)).isdecimal(): raise ValueError(f"{name} must be a whole number, not {value}")
  return int(value)

IT01_ENDPOINT = flag("IT01_ENDPOINT", "http://localhost:8080/v1/chat/completions")
IT01_MODEL = flag("IT01_MODEL", "local")
IT01_KEY = flag("IT01_KEY", "")
IT01_DEBUG = number("IT01_DEBUG", "0")
IT01_TIMEOUT = number("IT01_TIMEOUT", "120")

def data(name:str) -> dict[str, Any]:
  raw = json.loads((pathlib.Path(__file__).parent / f"{name}.json").read_text())
  if not isinstance(raw, dict): raise ValueError(f"{name}.json must hold a JSON object")
  return raw

def instruction(name:str) -> str:
  if not isinstance(text := data(name).get("instruction"), str): raise ValueError(f"{name}.json must hold an instruction string, not {text}")
  return text
