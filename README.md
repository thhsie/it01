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
it01 facts.json
```

It computes chargeable income, income tax, fair share contribution, total tax, the balance after tax already paid, and the losses to carry forward. Each figure prints with the sections behind it and a link to the page of the law.

## Pay the tax on a quarter

A person with rental income pays tax on each of the first three quarters of the year.

```sh
echo '{"resident": true, "dependants": 1, "rent": 400000, "period": "quarter"}' > q1.json
it01 q1.json
```

`period` is `year` unless you say otherwise. A quarter is taxed on its own bands and takes a quarter of the deduction for dependants. It credits the tax deducted at source in that quarter and owes no fair share contribution.

A quarter takes `rent`, `losses_brought_forward`, `tax_deducted_at_source` and `business`. Every other fact is refused by name. In a quarter, the allowance on an asset is a quarter of the annual allowance, and the figure is named that way.

## Drop a document in

```sh
export IT01_ENDPOINT=http://localhost:8080/v1/chat/completions IT01_MODEL=your-model
it01 add facts.json bank.txt
it01 keep facts.json
it01 confirm facts.json resident_dividends
```

The endpoint takes OpenAI-compatible chat requests and can be on your computer or on a server.

A document is read as text. A PDF can be given instead, and each of its pages is read off its picture, as described below.

`add` works out what the document is. A running balance column means a bank statement, which is labelled through your endpoint or a model file. Anything else is read with a model file of your own.

What it finds goes to `proposed`, with a note of where it came from. What it cannot place goes to `pending` as a question. A question you have already answered is not asked again, and the command says so. A figure for a name already proposed is added to it, and both notes are kept.

A document whose name is already in `documents` is not read at all, and the file is left alone. A file identical to one read before is refused the same way, whatever it is called. A figure for a fact you have confirmed becomes a question, so a second document never changes a confirmed figure on its own.

`keep` prints everything processed so far. `confirm` moves one figure into the facts, and nothing else does. `data` prints the same case as JSON, with every number as text.

`keep` also adds up the money paid in, by the kind it was labelled and by month. It also sums it by what it counts as: income, exempt, still to sort, or not income. A label that does not read as money paid in is listed, not counted. `data` carries the same totals.

The dates of a statement's labelled payments say which part is the month. A first part from 13 to 31 means the day comes first, and a second part from 13 to 31 means the month comes first. When the dates do not show the order, no payment from that statement is placed in a month, and `keep` lists them. A two-digit year is read as 20yy.

## Answer an open question

```sh
it01 answer facts.json "1,200.00 paid in on 12/08" "sold my old bicycle"
```

Give the start of the question's wording after the file. When it matches no question, or more than one, nothing changes and the command says so.

The question moves from `pending` to `answers` with the words you used. No figure moves. A question already answered is refused, so your first words are kept.

## Read with a model file of your own

```sh
pip install -e '.[local]'
export IT01_MODEL_FILE=reader.onnx IT01_TOKENISER=tokenizer.json
it01 local statement.txt
```

The `local` command takes an encoder that scores runs of words. It reads the document once and every answer points at a place in the text. The model is asked to fill one form, and the form's own sums decide between competing readings.

`it01/model.json` says what your file calls the nine things the package needs, along with the wording it expects. `it01/reading.json` holds the form, and the instruction the endpoint reader sends.

## Read a PDF off its pages

```sh
pip install -e '.[pdf,local]'
export IT01_DETECTOR=detector.onnx IT01_RECOGNISER=recogniser.onnx
it01 rows statement.pdf
```

Every page of a PDF is drawn as a picture and read with two model files. The text layer is not used, so a scan and a printed file are read the same way. A page on which nothing is read is refused, and the message names the page.

The detector takes the page at most 1280 pixels on its longest side, with each side a multiple of 32. It returns, for each pixel, the chance that it is part of a line of writing. The recogniser takes one line at 48 pixels tall. It returns the chance of each character at each step, where the first means no character and the last means a space.

The recogniser lists the characters it writes in its metadata, under `character`, one to a line. A list that does not match its output is refused. Both files take red, green and blue channels first, scaled from minus one to one.

## Read a bank statement

```sh
it01 rows statement.txt
it01 credits statement.txt
```

`rows` finds the columns from the arithmetic, checks each balance against the running total and marks each transaction `ok`, `does not agree` or `not checked`. Each transaction starts with the number of the line it was read from, counting from 1, as `it01 show` prints it. An amount it cannot place is counted, per page.

`credits` labels every payment in through your endpoint, or your model file when `IT01_LABELLER` is set. The kinds are in `it01/labelling.json`. `feeds` says which fact each kind adds to, and `asking` says which kinds it asks you about.

`not_income` names the kinds that are not income. Every kind must be fed, needed, exempt, asked about or not income.

## Label bank credits with a model file of your own

```sh
export IT01_LABELLER=labeller.onnx IT01_TOKENISER=tokenizer.json
it01 credits bank.txt
```

With `IT01_LABELLER` set, each credit is labelled by a classifier on this computer and the endpoint is not called. The file scores every kind in `it01/labelling.json` for one credit at a time, and the highest score wins.

`it01/labeller.json` says what your file calls its four inputs and its output, and how the prompt is laid out. The kinds, their descriptions and the examples come from `it01/labelling.json`. The labeller reads with the same `IT01_TOKENISER` as the reader.

## The facts file

Only `resident` is required. `dependants` is a count and `business` is an object. The rest are amounts, written as numbers with at most two decimal places.

```
salary                       taxable_transport_allowance  performance_bonus
statutory_bonus              other_income                 rent
losses_brought_forward       resident_dividends           housing_loan_interest
medical_insurance            other_reliefs                paye_withheld
tax_deducted_at_source       quarterly_tax_paid
```

`salary` holds all emoluments. `rent` holds income from letting. `other_income` holds income that is neither emoluments, rent nor business. `business` holds the accounts line by line as the return lists them, with an `assets` list for annual allowances.

Seven keys are set aside before the computation and none of them reaches it: `proposed`, `sources`, `documents`, `texts`, `paths`, `answers`, `pending`.

`paths` holds the full path each document was read from, so `it01 show` can print the document. `it01 show` refuses a document that is no longer at that path, and one whose file has changed since it was read.

## Keep your own copies

`it01/model.json`, `it01/reading.json` and `it01/labelling.json` ship as defaults and are meant to be changed. Set `IT01_DATA` to a folder of your own and a file found there is used instead of the one in the package. A name you do not put there still comes from the package.

```sh
mkdir -p ~/it01
cp "$(python -c 'import it01, pathlib; print(pathlib.Path(it01.__file__).parent)')/model.json" ~/it01/
export IT01_DATA=~/it01
```

A folder that is not there is refused.

## Commands

```
it01 FACTS.json                         compute the tax
it01 add FACTS.json DOCUMENT.txt        read a document into the file
it01 keep FACTS.json                    print everything so far
it01 show FACTS.json DOCUMENT.txt       print a document the way it was read
it01 confirm FACTS.json FACT            accept a proposed figure
it01 answer FACTS.json QUESTION ANSWER  answer an open question
it01 read DOCUMENT.txt                  propose facts through your endpoint
it01 local DOCUMENT.txt                 propose facts with your model file
it01 rows STATEMENT.txt                 read transactions
it01 credits STATEMENT.txt              label what was paid in
it01 data FACTS.json                    print the whole case as JSON
```

`IT01_KEY` is a bearer token if your endpoint needs one, `IT01_TIMEOUT` the seconds to wait, `IT01_DEBUG=2` prints the endpoint's reply. `IT01_DATA` is a folder holding your own copies of the JSON files in `it01/`.

## What it does not do yet

Reading through an endpoint does not read the business accounts or the number of dependants. It does not handle an exempt activity inside the business accounts. It does not handle the extra deductions for special categories of employees, nor the artist and fast charger deductions. It does not handle a balancing charge when an asset is sold.

It does not hold dividends that a body you belong to received and did not pay out, which the fair share contribution counts as yours.

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
