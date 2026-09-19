# it01

it01 prepares your income tax on your own computer.

## How it works

- A language model reads your documents and proposes facts. You confirm each fact before it is used.
- Deterministic Python code computes the tax from the confirmed facts. Each figure names the rule and the legal source it comes from, with a link to the source.
- The model is reached through an OpenAI-compatible endpoint that you configure. The endpoint can be on your computer or on a server.
- The package uses only the Python standard library. One module, `it01/llm.py`, uses the network, and only to call your configured endpoint. `test/test_privacy.py` checks this on every change.

## Status

The project is in early development. It computes chargeable income, income tax, fair share contribution, total tax, the balance after tax already paid and the losses to carry forward, for an individual with employment income, business income, other income and resident dividends. Business income is entered as gross income, the total of allowable deductions and the business assets that earn an annual allowance. It does not yet work out the allowable deductions from the accounts, or the balancing charge or allowance when an asset is sold.

## Usage

Write the facts in a JSON file. Amounts are numbers with at most two decimal places. Only `resident` is required.

```json
{"resident": true, "dependants": 1, "salary": 1200000}
```

The other facts are `taxable_transport_allowance`, `performance_bonus`, `statutory_bonus`, `other_income`, `business_gross_income`, `business_deductions`, `losses_brought_forward`, `resident_dividends`, `housing_loan_interest`, `medical_insurance`, `other_reliefs`, `paye_withheld`, `tax_deducted_at_source` and `quarterly_tax_paid`.

```sh
python -m it01 facts.json
```

Each figure is printed with the sections of the law it comes from and a link to each page.

`assets` lists the assets of the business, bought this year or earlier:

```json
{"resident": true, "business_gross_income": 900000, "assets": [{"kind": "computer", "cost": 80000}]}
```

Each asset has a `kind`, its `cost` net of any subsidy, grant or contribution, and `allowances_before`, the total annual allowance claimed on it in earlier years. The kinds are `industrial_premises`, `commercial_premises`, `hotel`, `ship_or_aircraft`, `motor_vehicle`, `computer`, `electronic_equipment`, `furniture`, `other_plant`, `agricultural_improvement`, `research_and_development`, `golf_course`, `patent`, `green_technology`, `landscaping`, `solar_energy_unit` and `other_capital_item`.

An allowance worked out at a rate is rounded down to whole rupees. The law sets a maximum rate, so a lower claim is allowed. Next year's `allowances_before` is this year's plus the allowance printed.

`salary` holds all emoluments, including pensions from past employment and benefits. `other_income` holds income other than emoluments and business income.

The balance of tax is tax to pay when positive, and tax paid in excess when negative. The losses carried forward can be set against income other than emoluments in the next 5 years. `losses_brought_forward` holds only losses that have not lapsed. Losses brought forward are used before the loss of the year, oldest first.

## Development

```sh
pip install -e '.[linting]'
python -m ruff check . && python -m mypy && python -m unittest && MAX_LINE_COUNT=3000 python sz.py
```

## Contributing

Fixes and updates to the tax rules are welcome. Read [AGENTS.md](AGENTS.md) before you contribute. Its rules apply to all contributions.

## License

MIT
