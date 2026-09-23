# it01

it01 prepares your income tax on your own computer.

## How it works

- A language model reads your documents and proposes facts. You confirm each fact before it is used.
- Deterministic Python code computes the tax from the confirmed facts.
- Each figure names the rule and the legal source it comes from, with a link.
- The model is reached through an OpenAI-compatible endpoint that you configure.
- The endpoint can be on your computer or on a server.
- The package uses only the Python standard library.
- One module, `it01/llm.py`, uses the network, and only to call your endpoint.
- `test/test_privacy.py` checks that on every change.
- Working out a tax result needs no install beyond the package.
- Reading with a model file of your own needs `pip install it01[local]`.
- That extra adds a model runtime and a tokeniser, and only `it01/local.py` imports them.

## Status

The project is in early development.

It computes chargeable income, income tax, fair share contribution and total tax. It computes the balance after tax already paid and the losses to carry forward. It covers an individual with employment income, business income, other income and resident dividends.

It does not yet handle income from an exempt activity inside the business accounts. It does not handle the extra deductions for special categories of employees. It does not handle the artist and fast charger deductions. It does not handle a balancing charge or allowance when an asset is sold.

Reading through an endpoint proposes the amounts on the facts list below. It does not read the business accounts or the number of dependants. Reading with a model file proposes the lines of one form.

## Reading a document

Save the document as text. Ask the model to propose facts from it.

```sh
export IT01_ENDPOINT=http://localhost:8080/v1/chat/completions
export IT01_MODEL=your-model
python -m it01 read statement.txt
```

Each proposal is printed with the line of the document it was read from. Nothing is computed from a proposal. Copy the ones you accept into your facts file.

A proposal is refused unless its quote is one of the document's lines showing the figure. An amount is refused unless it is a plain figure of at most two decimal places. It is held to the same limits as a fact you write yourself. A fact name the package does not know is refused.

The package does not retry and does not repair an answer.

The endpoint is read from `IT01_ENDPOINT` and the model name from `IT01_MODEL`. `IT01_KEY` is a bearer token if your endpoint needs one. `IT01_TIMEOUT` is the seconds to wait, 120 by default. `IT01_DEBUG=2` prints the endpoint's reply.

The instruction sent to the model is in `it01/reading.json`. Change it to suit your model.

## Reading with a model of your own

The reading above takes any model that answers chat requests. This way takes an encoder. It reads the document once and scores runs of words. Every answer points at a place in the text.

```sh
pip install 'it01[local]'
export IT01_MODEL_FILE=reader.onnx
export IT01_TOKENISER=tokenizer.json
python -m it01 local statement.txt
```

The model is asked to fill in one form. It is asked for as many lines at a time as the `lines` input holds. A file with a slot for every line asks them all at once.

What is printed is the facts, then any questions, then the sums the form works out for itself.

```
salary                              1,107,000.00
  net_emoluments, 1,107,000.00
paye_withheld                          71,401.00
  tax_withheld, 71,401.00

the form's own working
  total says 1,227,000.00 and adds to 1,227,000.00  ok
  net_emoluments says 1,107,000.00 and adds to 1,107,000.00  ok
```

Under each fact is the form line and the words it came from. An answer the model is less than half sure of is left out before any of this.

The model often claims one figure under several lines. Every way of sharing those figures among the claiming lines is tried.

A line the reader missed looks the same as a line the form leaves blank. A missing added line can only make a sum too small. A missing subtracted line can only make it too big. A way is thrown out when a sum is wrong in the direction no missing line could explain.

A figure with one line left becomes a fact. A figure no surviving way uses is dropped. A figure with two or more lines left goes under `questions`, with the wording of each line.

A fact is told only when every figure that could feed it settles on one amount. Otherwise all of them are asked about. When too many figures are contested to work through, none of the contested ones is settled.

One sum adds the lines that make the total. The other takes the total less the exempt income.

Each prints `ok` when it comes out. It prints `does not agree` when no missing line could explain the difference. It prints `not checked` when one could.

The sums are read from the surviving way that makes the most of them come out. When no way survives they are read from the figures only one line claims, and that no question is about. A sum is left out when the line it works out was not found. It is left out when none of the lines it adds and takes away was found.

Two of the form's lines feed a fact and the rest do not. The emoluments net of exempt income go to `salary`. The tax withheld goes to `paye_withheld`. Writing any other emoluments line as well would count it twice.

The reliefs line and the retirement fund line feed nothing. The facts file works the dependant deduction out from `dependants`. Medical and housing loan reliefs have facts of their own. The employee claims no deduction for the employer's fund contributions.

Two files say how a document is read.

`it01/reading.json` holds the form under `form`. It carries the form's name, its lines in order, what each line means, the `feeds` mapping and the `checks` sums. The lines shipped are the lines of a statement of emoluments. Change them to read a different document.

`it01/model.json` holds what your file calls the nine things the package needs. It also holds the wording your model expects, in four parts. It holds the two marks inside that wording, the one starting a line and the one starting the document. `word_start` is the character your tokeniser puts at the start of a word.

Your file has to provide those nine. Six go in, called `tokens`, `attention`, `words`, `word_mask`, `lines` and `line_mask` here. Each is two-dimensional and fixed in size. Three come back, called `spans`, `scores` and `valid` here.

`spans` has four dimensions and the other two have three. `scores` are logits. A file that already gives a probability reports the wrong confidence. `valid` says which answers to keep, and one it does not mark is left out.

A document too long for the file is read in windows that overlap by a quarter of their length. An answer touching the edge of a window is left out when there is another window on that side. The figure is taken from that window instead, unless its words run longer than the overlap.

Several things are refused rather than guessed, each naming what is wrong.

- A model file or tokeniser that is not named, or named and not there.
- A model file whose inputs or outputs are not the nine names in `it01/model.json`.
- A model file whose inputs are not two-dimensional, or not of fixed size.
- A model file that answers in a shape this does not read.
- A tokeniser that does not know the marks your wording uses.
- A tokeniser that splits the document into words `word_start` does not match.
- A tokeniser that marks a different number of lines than the form has.
- An `it01/model.json` missing a name, a part of the wording, a mark, or `word_start`.
- An `it01/model.json` naming a mark the wording never writes.
- An `it01/model.json` whose wording leaves out or adds a name the package fills in.
- An `it01/reading.json` form with no name, or a line with no description.
- A `feeds` that is not an object from a line to a fact.
- A feed naming a line the form does not have, or a fact the facts file does not take.
- A feed sending two lines to one fact.
- A `checks` that is not a list of sums.
- A sum that does not say which line it works out.
- A sum that adds or takes away something which is not a line name.
- A sum naming a line the form does not have, or working a line out from itself.
- A sum that adds and takes away nothing.
- A document with no words, or one whose form leaves no room for any of it.

An answer reaching past the last word is left out instead. So is one whose words do not read as a figure. The rest of the document is still read.

Only `it01/local.py` imports the runtime and the tokeniser, and only under the `local` extra.

## Reading a bank statement

Save the statement as text, keeping the layout. Read its transactions. No model is used and nothing leaves your computer.

```sh
python -m it01 rows statement.txt
```

Each transaction is printed with its date, the amount paid out or in, the balance after it, and its description.

The columns are worked out from the statement itself. A column is taken as the running balance when at least three in five of the changes between its amounts are matched. A match is a single amount printed on the lines between. Those matching amounts are the transactions.

A balance that does not change is counted on neither side. Two changes are the fewest that can be matched. A column of two amounts is never a running balance.

Each page is worked out on its own. Pages are split on the form feed that a text extractor writes. A page with too few amounts uses the columns found across the whole statement.

The headings say which column is which. On each page every money column takes the heading printed nearest to it, within a few characters either side. The row that names the most columns is the one that counts. The larger side across the statement decides.

A page that had too few amounts to work out on its own casts no vote. The statement is refused when the count is tied. It is refused when no heading is recognised. It is refused when two rows tied at the top name the columns in opposite orders.

The headings decide which column is money out and which is money in. A statement whose headings are printed the wrong way round still adds up. The balance check cannot catch that.

The check compares each balance with the running total. Each transaction is marked `ok` when the balance follows. It is marked `does not agree` when it does not. It is marked `not checked` when there is no balance to compare with.

An amount with no balance after it is added to the transaction that follows. A subtotal printed in a money column is such an amount. That transaction is then marked `does not agree` when there is a running total.

Several transactions printed under one balance are reported as one line, with the amounts added together. A line that only carries a balance forward is not printed. It is printed and marked `does not agree` when the balance it carries does not follow.

An amount is read only when it is printed with two decimal places and is not followed by a percent sign. So a reference number printed without decimals, or a rate written with a percent sign, is not mistaken for money. An amount in brackets or with a trailing minus is a negative balance.

In a money column such an amount is reported in that column's direction, without its sign. Its balance will not follow, and the transaction is marked `does not agree` when there is a running total. An amount in a column that explains no balance change is left out. A transaction that owned such an amount then fails its balance check, when there is a running total.

A statement with no amounts at all is refused. So is one with no running balance column anywhere. On a statement that has one, a page with no running balance column loses all of its amounts. An amount that fits no column is left out, and each page reports how many it lost.

## Labelling what was paid in

After a statement reads into transactions, each credit is labelled through your endpoint. The credits only you can explain are printed as questions.

```sh
python -m it01 credits statement.txt
```

Only money paid in is sent. Each credit goes with its date, its amount and its description, numbered. The model answers with a kind for each number.

The kinds and what they mean are in `it01/labelling.json`. Change them to suit your affairs.

The totals for each kind are printed, and the number of credits in each. A kind holding a credit with no balance that agrees says how many. Nothing is computed from them. Copy the ones you accept into your facts file.

Two kinds cannot be settled from the wording. A cash deposit does not say where the money came from. Neither does a credit whose wording explains nothing.

Both are printed under `questions` with the date, the amount, what to ask yourself and the wording. They do not stop the rest being read.

An answer is refused unless it names every credit exactly once and uses only the kinds in the file. The package does not retry and does not repair an answer.

## Usage

Write the facts in a JSON file. Amounts are numbers with at most two decimal places. Only `resident` is required.

```json
{"resident": true, "dependants": 1, "salary": 1200000}
```

The other facts are:

```
taxable_transport_allowance  performance_bonus            statutory_bonus
other_income                 losses_brought_forward       resident_dividends
housing_loan_interest        medical_insurance            other_reliefs
paye_withheld                tax_deducted_at_source       quarterly_tax_paid
business
```

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

The trading lines are:

```
gross_income   cost_of_sales  other_income
```

Gross profit is `gross_income` less `cost_of_sales`. `other_income` is added after it.

The expenses are:

```
wages                              professional_expenses
entertainment_gifts_and_donations  advertising
overseas_travel                    interest
bank_charges                       utilities
rent                               licences_and_taxes
motor_vehicle_expenses             repairs
depreciation                       bad_debts
other_expenses
```

The two lines added back are:

```
income_not_in_accounts  non_allowable_expenses
```

Depreciation and entertainment, gifts and donations are added back on their own. Do not enter them in `non_allowable_expenses`. The law never allows them.

`non_allowable_expenses` holds the rest that the law does not allow, such as the private part of an expense, a provision, or spending of a capital nature.

The printed figures follow the return. They are gross profit, net profit per accounts, and non-allowable expenses including the amounts added back. Then the annual allowance on each asset, and net income from business.

`assets` lists the assets of the business, bought this year or earlier. Each asset has a `kind` and its `cost` net of any subsidy, grant or contribution. It also has `allowances_before`, the total annual allowance claimed on it in earlier years.

The kinds are:

```
industrial_premises       commercial_premises       hotel
ship_or_aircraft          motor_vehicle             computer
electronic_equipment      furniture                 other_plant
agricultural_improvement  research_and_development  golf_course
patent                    green_technology          landscaping
solar_energy_unit         other_capital_item
```

An allowance worked out at a rate is rounded down to whole rupees. The law sets a maximum rate, so a lower claim is allowed. Next year's `allowances_before` is this year's plus the allowance printed.

## The record to keep

When the return is filed, print what you confirmed and keep it.

```sh
python -m it01 keep facts.json
```

It prints the facts you confirmed and the wording each came from. It prints every figure with the rule and the section of law behind it. It prints the figures proposed, the documents you read, the questions you answered and the questions still open.

Five optional keys in the file are set aside before the computation. None of them reaches it, so adding them cannot change a figure.

```json
{
  "resident": true,
  "salary": 1107000,
  "proposed": {"other_income": 40000},
  "sources": {"salary": "Total emoluments        1,107,000.00", "other_income": "Rent received 40,000.00"},
  "documents": {"statement.txt": "statement of emoluments"},
  "answers": {"05/07/2025 500.00 where did this cash come from": "sold my old bicycle"},
  "pending": {"12/08/2025 1,200.00 where did this cash come from": "ask the bank for the payer"}
}
```

`proposed` holds a figure read from a document that you have not yet accepted. It is printed under its own heading, apart from the facts. A name that is not a fact is refused. So is a figure that would be refused as a fact, and a name the file already gives as a fact.

`sources` maps a fact to the line it was read from. It may name a proposed figure instead. A name that is neither is refused. So is naming the business, since a business line carries no wording of its own.

`documents` maps a document you have read to what it was. `answers` maps a question you were asked to what you replied. `pending` maps a question still open to what to do about it.

Those four hold text against text. A blank key or a blank value is refused in any of them. The same key written twice is refused anywhere in the file.

The command that computes the tax reads the same file. All five keys are set aside before the facts are computed.

Reading a document into the file needs the model file above.

```sh
python -m it01 add facts.json statement.txt
```

The document is recorded under `documents` with the form it was read as. Each figure the reader settles is written to `proposed`, with the line it came from written to `sources`. Each figure it cannot settle is written to `pending` as a question.

A figure the file already gives, as a fact or as a proposal, is not written again. A figure that disagrees with one the file gives becomes a question naming both. Nothing already in the file is overwritten. Reading the same question again with different wording is refused.

Accepting a proposed figure moves it among the facts.

```sh
python -m it01 confirm facts.json other_income
```

The figure leaves `proposed` and becomes a fact under the same name. Its wording stays where it was. A name that is not proposed is refused. No other command moves a figure into the facts.

The file is rewritten in place, with the facts first and the five keys after them. Amounts keep the digits you wrote. Your spacing and key order are not kept, and a key holding nothing is dropped. A write that fails leaves the original beside a file named for it, ending in `.new`.

## Development

```sh
pip install -e '.[linting]'
python -m ruff check . && python -m mypy && python -m unittest && MAX_LINE_COUNT=3000 python sz.py
```

## Contributing

Fixes and updates to the tax rules are welcome. Read [AGENTS.md](AGENTS.md) before you contribute. Its rules apply to all contributions.

## License

MIT
