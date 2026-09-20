# it01

it01 prepares your income tax on your own computer.

## How it works

- A language model reads your documents and proposes facts. You confirm each fact before it is used.
- Deterministic Python code computes the tax from the confirmed facts. Each figure names the rule and the legal source it comes from, with a link to the source.
- The model is reached through an OpenAI-compatible endpoint that you configure. The endpoint can be on your computer or on a server.
- The package uses only the Python standard library. One module, `it01/llm.py`, uses the network, and only to call your configured endpoint. `test/test_privacy.py` checks this on every change.

## Status

The project is in early development. It computes chargeable income, income tax, fair share contribution, total tax, the balance after tax already paid and the losses to carry forward, for an individual with employment income, business income, other income and resident dividends. It does not yet handle income from an exempt activity inside the business accounts, the extra deductions for special categories of employees, the artist and fast charger deductions, or the balancing charge or allowance when an asset is sold. Reading proposes the amounts on the facts list below, not the business accounts and not the number of dependants.

## Reading a document

Save the document as text, then ask the model to propose facts from it.

```sh
export IT01_ENDPOINT=http://localhost:8080/v1/chat/completions
export IT01_MODEL=your-model
python -m it01 read statement.txt
```

Each proposal is printed with the line of the document it was read from. Nothing is computed from a proposal. Copy the ones you accept into your facts file.

A proposal is refused unless its quote is one of the document's lines and that line shows the figure. An amount is refused unless it is a plain figure of at most two decimal places, and it is held to the same limits as a fact you write yourself. A fact name the package does not know is refused. The package does not retry and does not repair an answer.

The endpoint is read from `IT01_ENDPOINT`, the model name from `IT01_MODEL`, and a bearer token from `IT01_KEY` if your endpoint needs one. `IT01_TIMEOUT` is the number of seconds to wait for an answer, 120 by default. `IT01_DEBUG=2` prints the endpoint's reply.

The instruction sent to the model is in `it01/reading.json`. Change it to suit your model.

## Usage

Write the facts in a JSON file. Amounts are numbers with at most two decimal places. Only `resident` is required.

```json
{"resident": true, "dependants": 1, "salary": 1200000}
```

The other facts are `taxable_transport_allowance`, `performance_bonus`, `statutory_bonus`, `other_income`, `losses_brought_forward`, `resident_dividends`, `housing_loan_interest`, `medical_insurance`, `other_reliefs`, `paye_withheld`, `tax_deducted_at_source`, `quarterly_tax_paid` and `business`.

```sh
python -m it01 facts.json
```

Each figure is printed with the sections of the law it comes from and a link to each page.

`salary` holds all emoluments, including pensions from past employment and benefits. `other_income` holds income other than emoluments and business income.

The balance of tax is tax to pay when positive, and tax paid in excess when negative. The losses carried forward can be set against income other than emoluments in the next 5 years. `losses_brought_forward` holds only losses that have not lapsed. Losses brought forward are used before the loss of the year, oldest first.

### Business

`business` holds the business accounts, line by line as the return lists them:

```json
{"resident": true, "business": {"gross_income": 900000, "professional_expenses": 50000, "assets": [{"kind": "computer", "cost": 80000}]}}
```

The lines are `gross_income`, `cost_of_sales`, `other_income`, the expenses `wages`, `professional_expenses`, `entertainment_gifts_and_donations`, `advertising`, `overseas_travel`, `interest`, `bank_charges`, `utilities`, `rent`, `licences_and_taxes`, `motor_vehicle_expenses`, `repairs`, `depreciation`, `bad_debts` and `other_expenses`, then `income_not_in_accounts` and `non_allowable_expenses`.

Depreciation and entertainment, gifts and donations are added back without being entered in `non_allowable_expenses`, because the law never allows them. `non_allowable_expenses` holds the rest that the law does not allow: the private part of an expense, a provision, or spending of a capital nature.

The printed figures follow the return: gross profit, net profit per accounts, non-allowable expenses including the amounts added back, the annual allowance on each asset, and net income from business.

`assets` lists the assets of the business, bought this year or earlier. Each asset has a `kind`, its `cost` net of any subsidy, grant or contribution, and `allowances_before`, the total annual allowance claimed on it in earlier years. The kinds are `industrial_premises`, `commercial_premises`, `hotel`, `ship_or_aircraft`, `motor_vehicle`, `computer`, `electronic_equipment`, `furniture`, `other_plant`, `agricultural_improvement`, `research_and_development`, `golf_course`, `patent`, `green_technology`, `landscaping`, `solar_energy_unit` and `other_capital_item`.

An allowance worked out at a rate is rounded down to whole rupees. The law sets a maximum rate, so a lower claim is allowed. Next year's `allowances_before` is this year's plus the allowance printed.

## Development

```sh
pip install -e '.[linting]'
python -m ruff check . && python -m mypy && python -m unittest && MAX_LINE_COUNT=3000 python sz.py
```

## Contributing

Fixes and updates to the tax rules are welcome. Read [AGENTS.md](AGENTS.md) before you contribute. Its rules apply to all contributions.

## License

MIT
