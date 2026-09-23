# it01

it01 prepares an individual's income tax on your own computer. A model reads your documents and proposes facts. Plain Python computes the tax from the facts you confirm.

- **Readers** turn a document into proposed figures, each with a note of where it came from.
- **A case file** holds what was read, what is proposed, what you confirmed and what is still open.
- **Every figure** names the rule and the section of law behind it.
- **No network** is used beyond the model endpoint you configure.

A model never decides tax. Nothing it proposes reaches the computation until you confirm it.

---

## Try it

```sh
git clone https://github.com/thhsie/it01 && cd it01
pip install -e .
echo '{"resident": true, "dependants": 1, "salary": 1200000}' > facts.json
python -m it01 facts.json
```

It computes chargeable income, income tax, fair share contribution, total tax, the balance after tax already paid, and the losses to carry forward. Each figure prints with the sections behind it and a link to the page of the law.

## Drop a document in

```sh
export IT01_ENDPOINT=http://localhost:8080/v1/chat/completions IT01_MODEL=your-model
python -m it01 add facts.json bank.txt
python -m it01 keep facts.json
python -m it01 confirm facts.json resident_dividends
```

The endpoint takes OpenAI-compatible chat requests and can be on your computer or on a server.

`add` works out what the document is. A running balance column means a bank statement, which is labelled through your endpoint. Anything else is read with a model file of your own.

What it finds goes to `proposed`, with a note of where it came from. What it cannot place goes to `pending` as a question. Nothing is overwritten, and a figure that disagrees with the file becomes a question naming both.

`keep` prints everything processed so far. `confirm` moves one figure into the facts, and nothing else does.

## Read with a model file of your own

```sh
pip install -e '.[local]'
export IT01_MODEL_FILE=reader.onnx IT01_TOKENISER=tokenizer.json
python -m it01 local statement.txt
```

The `local` command takes an encoder that scores runs of words. It reads the document once and every answer points at a place in the text. The model is asked to fill one form, and the form's own sums decide between competing readings.

`it01/model.json` says what your file calls the nine things the package needs, along with the wording it expects. `it01/reading.json` holds the form, and the instruction the endpoint reader sends. Both are yours to change.

## Read a bank statement

```sh
python -m it01 rows statement.txt
python -m it01 credits statement.txt
```

`rows` finds the columns from the arithmetic, checks each balance against the running total and marks each transaction `ok`, `does not agree` or `not checked`. An amount it cannot place is counted, per page.

`credits` labels every payment in through your endpoint. The kinds are in `it01/labelling.json`. `feeds` says which fact each kind adds to, and `asking` says which kinds it asks you about.

## The facts file

Only `resident` is required. `dependants` is a count and `business` is an object. The rest are amounts, written as numbers with at most two decimal places.

```
salary                       taxable_transport_allowance  performance_bonus
statutory_bonus              other_income                 losses_brought_forward
resident_dividends           housing_loan_interest        medical_insurance
other_reliefs                paye_withheld                tax_deducted_at_source
quarterly_tax_paid
```

`salary` holds all emoluments. `business` holds the accounts line by line as the return lists them, with an `assets` list for annual allowances.

Five keys are set aside before the computation and none of them reaches it: `proposed`, `sources`, `documents`, `answers`, `pending`.

## Commands

```
python -m it01 FACTS.json                    compute the tax
python -m it01 add FACTS.json DOCUMENT.txt   read a document into the file
python -m it01 keep FACTS.json               print everything so far
python -m it01 confirm FACTS.json FACT       accept a proposed figure
python -m it01 read DOCUMENT.txt             propose facts through your endpoint
python -m it01 local DOCUMENT.txt            propose facts with your model file
python -m it01 rows STATEMENT.txt            read transactions
python -m it01 credits STATEMENT.txt         label what was paid in
```

`IT01_KEY` is a bearer token if your endpoint needs one, `IT01_TIMEOUT` the seconds to wait, `IT01_DEBUG=2` prints the endpoint's reply.

## What it does not do yet

Reading through an endpoint does not read the business accounts or the number of dependants. It does not handle an exempt activity inside the business accounts. It does not handle the extra deductions for special categories of employees, nor the artist and fast charger deductions. It does not handle a balancing charge when an asset is sold.

## Development

```sh
pip install -e '.[linting]'
python -m ruff check . && python -m mypy && python -m unittest && MAX_LINE_COUNT=3000 python sz.py
```

Every check passes before a commit. There is no formatter. Do not run one.

## Contributing

Fixes and updates to the tax rules are welcome. Read [AGENTS.md](AGENTS.md) first, because its rules bind every change.

No code golf. Line count is how complexity is measured here, and deleting a newline does nothing for readability.

Every bug fix ships a test that fails without it. A refactor is its own pull request and changes no computed result. Say in a sentence or two why your change should be merged.

## License

MIT
