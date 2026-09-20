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

## Reading a bank statement

Save the statement as text, keeping the layout, then read its transactions. No model is used and nothing leaves your computer.

```sh
python -m it01 rows statement.txt
```

Each transaction is printed with its date, the amount paid out or in, the balance after it, and its description.

The columns are worked out from the statement itself. A column is taken as the running balance when at least three in five of the changes between its amounts are matched by a single amount printed on the lines between. A balance that does not change is counted on neither side, and two changes are the fewest that can be matched, so a column of two amounts is never a running balance. The amounts that match those changes are the transactions.

Each page is worked out on its own, because a statement can change its layout between pages. Pages are split on the form feed that a text extractor writes. A page with too few amounts to work out uses the columns found across the whole statement.

The headings say which column is which. On each page every column looks for the heading printed nearest to it, on any row of that page, within a few characters either side. The row that names the most columns is the one that counts. A page that had too few amounts to work out on its own does not count at all. The larger side across the statement decides. The statement is refused when the count is tied, when no heading is recognised, or when two rows tied at the top count name the columns in opposite orders.

The headings decide which column is money out and which is money in. The balance check cannot catch a statement whose headings are printed the wrong way round, because the amounts still add up either way.

The check compares each balance with the running total, so it does not depend on the headings. Each transaction is marked `ok` when the balance follows, `does not agree` when it does not, and `not checked` when there is no balance to check it against. An amount with no balance after it, such as a subtotal printed in a money column, is added to the transaction that follows it, and that transaction is marked `does not agree` when there is a running total to compare with.

Several transactions printed under one balance are reported as one line with the amounts added together. A line that only carries a balance forward is not a transaction and is not printed, unless the balance it carries does not follow, in which case it is printed and marked `does not agree`.

An amount is read only when it is printed with two decimal places and is not followed by a percent sign, so a reference number or a rate is not mistaken for money. An amount in brackets or with a trailing minus is a negative balance. In a money column such an amount is reported in that column's direction, without its sign, so its balance will not follow and the transaction is marked `does not agree`. An amount in a column that explains no balance change is left out. If such an amount belonged to a transaction, that transaction's balance check fails.

A statement with no amounts at all is refused, and so is a page whose amounts stand under no running balance.

## Labelling what was paid in

After a statement reads into transactions, each credit is labelled through your endpoint. The credits only you can explain are printed as questions.

```sh
python -m it01 credits statement.txt
```

Only money paid in is sent. Each credit goes with its date, its amount and its description, numbered, and the model answers with a kind for each number. The kinds and what they mean are in `it01/labelling.json`. Change them to suit your affairs.

The totals for each kind are printed, and the number of credits in each. A kind holding a credit whose balance did not agree says how many. Nothing is computed from them. Copy the ones you accept into your facts file.

Two kinds cannot be settled from the wording. A cash deposit does not say where the money came from, and neither does a credit whose wording explains nothing. Both are printed under `questions` with the date, the amount, what to ask yourself and the wording. They do not stop the rest being read.

An answer is refused unless it names every credit exactly once and uses only the kinds in the file. The package does not retry and does not repair an answer.

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
