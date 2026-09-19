# it01

Local-first income tax preparation for individuals.

it01 reads your documents, proposes the facts it finds, and computes your tax from the facts you confirm. It runs on your machine.

## Principles

- **A model never decides tax.** A language model turns documents into proposed facts. Plain, tested, deterministic code turns confirmed facts into a tax position, and every figure names the rule and the legal source it comes from.
- **Your data stays with you.** The package depends on nothing but the Python standard library. One module may use the network, only to reach the model endpoint you configure, and `test/test_privacy.py` enforces it on every commit.
- **Bring your own model.** Point it at any chat-completions endpoint, on your machine or elsewhere.

## Status

Scaffold. Nothing to run yet.

## Development

```sh
pip install -e '.[linting]'
python -m ruff check . && python -m mypy && python -m unittest && MAX_LINE_COUNT=3000 python sz.py
```

## Contributing

Fixes and updates to the tax rules are welcome. Read [AGENTS.md](AGENTS.md) first: its rules apply to every contribution, written by a person or not.

## License

MIT
