import json, os, pathlib

def flag(name:str, default:str) -> str: return os.environ.get(name, default)

def number(name:str, default:str) -> int:
  if not (value := flag(name, default)).isdecimal(): raise ValueError(f"{name} must be a whole number, not {value}")
  return int(value)

IT01_ENDPOINT = flag("IT01_ENDPOINT", "http://localhost:8080/v1/chat/completions")
IT01_MODEL = flag("IT01_MODEL", "local")
IT01_KEY = flag("IT01_KEY", "")
IT01_DEBUG = number("IT01_DEBUG", "0")
IT01_TIMEOUT = number("IT01_TIMEOUT", "120")

def instruction() -> str:
  raw = json.loads((pathlib.Path(__file__).parent / "reading.json").read_text())
  if not isinstance(text := raw.get("instruction"), str): raise ValueError(f"reading.json must hold an instruction string, not {text}")
  return text
