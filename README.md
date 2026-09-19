# it01

it01 prepares your income tax on your own computer.

## How it works

- A language model reads your documents and proposes facts. You confirm each fact before it is used.
- Deterministic Python code computes the tax from the confirmed facts. Each figure names the rule and the legal source it comes from, with a link to the source.
- The model is reached through an OpenAI-compatible endpoint that you configure. The endpoint can be on your computer or on a server.
- The package uses only the Python standard library. One module, `it01/llm.py`, uses the network, and only to call your configured endpoint. `test/test_privacy.py` checks this on every change.

## Status

The project is in early development. There is nothing to run yet.

## Development

```sh
pip install -e '.[linting]'
python -m ruff check . && python -m mypy && python -m unittest && MAX_LINE_COUNT=3000 python sz.py
```

## Contributing

Fixes and updates to the tax rules are welcome. Read [AGENTS.md](AGENTS.md) before you contribute. Its rules apply to all contributions.

## License

MIT
