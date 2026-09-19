# it01

it01 prepares your income tax on your own computer.

## How it works

- A language model reads your documents and proposes facts. You confirm each fact before it is used.
- Deterministic Python code computes the tax from the confirmed facts. Each figure names the rule and the legal source it comes from, with a link to the source.
- The model is reached through an OpenAI-compatible endpoint that you configure. The endpoint can be on your computer or on a server.
- The package uses only the Python standard library. One module, `it01/llm.py`, uses the network, and only to call your configured endpoint. `test/test_privacy.py` checks this on every change.

## Status

The project is in early development. It computes chargeable income, income tax, fair share contribution, total tax and the balance after tax already paid, for an individual with employment income, other income and resident dividends. It does not yet handle business income.

## Usage

Write the facts in a JSON file. Amounts are numbers with at most two decimal places. Only `resident` is required.

```json
{"resident": true, "dependants": 1, "salary": 1200000}
```

The other facts are `taxable_transport_allowance`, `performance_bonus`, `statutory_bonus`, `other_income`, `resident_dividends`, `housing_loan_interest`, `medical_insurance`, `other_reliefs`, `paye_withheld`, `tax_deducted_at_source` and `quarterly_tax_paid`.

```sh
python -m it01 facts.json
```

Each figure is printed with the sections of the law it comes from and a link to each page.

The last figure is the balance of tax. A positive balance is tax to pay. A negative balance is tax paid in excess.

## Development

```sh
pip install -e '.[linting]'
python -m ruff check . && python -m mypy && python -m unittest && MAX_LINE_COUNT=3000 python sz.py
```

## Contributing

Fixes and updates to the tax rules are welcome. Read [AGENTS.md](AGENTS.md) before you contribute. Its rules apply to all contributions.

## License

MIT
