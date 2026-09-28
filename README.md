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

`keep` also adds up the money paid in by the kind it was labelled. It also sums it by what it counts as: income, exempt, still to sort, or not income. A label that does not read as money paid in is listed, not counted. `data` carries the same totals.

The dates of a statement's labelled payments say which part is the month. A first part from 13 to 31 means the day comes first, and a second part from 13 to 31 means the month comes first. When the dates do not show the order, no payment from that statement is placed in a month, and `keep` lists them. A two-digit year is read as 20yy.

Money paid in is also added up for each month of one income year. The Act's year starts on 1 July, and the year shown holds the latest payment. A payment dated before that year is listed. `data` also gives, for each month, its sums by group and the labels in each sum.

## Answer an open question

```sh
it01 answer facts.json "1,200.00 paid in on 12/08" "sold my old bicycle"
```

Give the start of the question's wording after the file. When it matches no question, or more than one, nothing changes and the command says so.

The question moves from `pending` to `answers` with the words you used. An answer that names a kind of payment, or one of the listed lines that feeds a fact, proposes the amount under that fact.

A line the question did not list is refused. Any other answer is kept as a note and moves no figure. A question already answered is refused, so your first words are kept.

`it01 keep` prints what each answer would change in the tax to pay. It does this for a payment asked about, a figure read twice, a line of a form and a relief found in money paid out. The change is worked out from the facts you confirmed.

## Fill in the return

```sh
it01 sheet facts.json
```

This prints what to type in the return, one field a line, in the order the return asks for them. Each line gives the return's own field id and the value. The table that maps facts to fields is `it01/portal.json`.

The last lines are the return's own totals, so you can check them after typing. The return keeps whole amounts and drops the fraction as you type.

Some lines end with `filled in by the return, check it`. The return fills those fields itself. Check that each figure matches your document. A line ending with `the total of all rows` belongs to a table with one row per employer or payer, so split it across the rows as your documents do.

Facts the return has no single field for are listed last, with where to enter them. The sheet refuses a quarter, because the return takes a year.

## Change a payment's kind

```sh
it01 change facts.json "1,200.00 paid in on 12/08" rent
```

`change` gives an answered payment another kind. The amount the old kind added to a proposed figure is taken back. The new kind adds the amount to its own proposed figure, if it has one.

A figure you have confirmed is left alone, and the change is refused. Only a kind can replace an answer.

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
it01 debits statement.txt
```

`rows` finds the columns from the arithmetic, checks each balance against the running total and marks each transaction `ok`, `does not agree` or `not checked`. Each transaction starts with the number of the line it was read from, counting from 1, as `it01 show` prints it. An amount it cannot place is counted, per page.

`credits` labels every payment in through your endpoint, or your model file when `IT01_LABELLER` is set. The kinds are in `it01/labelling.json`. `feeds` says which fact each kind adds to, and `asking` says which kinds it asks you about.

`not_income` names the kinds that are not income. Every kind must be fed, needed, exempt, asked about or not income.

`debits` labels every payment out the same way, with the kinds in `it01/paying.json`, and prints the total of each kind. Most kinds match a relief in the law, such as a pension contribution or school fees. A label proposes no fact.

`it01 add` asks one question for each kind of payment out in a statement. `claims` names the kinds a yes adds to a fact, with the condition the law sets. `certificates` names the kinds whose figure comes from a certificate, and asks for it.

`business` names the kinds asked about only when the case has business income. A yes adds the total to the accounts line it names, and a typed amount adds only that part. `aside` names the kinds that count for nothing. A payment whose balance does not agree is left out of the totals.

A question about money paid out, a missing statement or a balance that does not agree lists its answers after a colon. Each answer says what it does. A question about a payment in takes one of the kinds `it01 add` prints. A question saved before its answers were listed shows them when the case is read.

## Label bank credits with a model file of your own

```sh
export IT01_LABELLER=labeller.onnx IT01_TOKENISER=tokenizer.json
it01 credits bank.txt
```

With `IT01_LABELLER` set, each credit is labelled by a classifier on this computer and the endpoint is not called. The file scores every kind in `it01/labelling.json` for one credit at a time, and the highest score wins.

`it01/labeller.json` says what your file calls its four inputs and its output, and the marks and wording around each kind and example. The task name, the instruction and the layout of one credit are under `model` in `it01/labelling.json`. The kinds, their descriptions and the examples are there too. The labeller reads with the same `IT01_TOKENISER` as the reader.

`debits` reads with the same model file. The task, the instruction, the line layout and the kinds are in `it01/paying.json`.

## The facts file

Only `resident` is required. `dependants` is a count and `business` is an object.

`medical_insurance` is a list of premiums, one per insured person: you first, then each dependant in order. It holds at most five, for you and four dependants. The rest are amounts, written as numbers with at most two decimal places.

```
salary                       taxable_transport_allowance  performance_bonus
statutory_bonus              other_income                 rent
losses_brought_forward       resident_dividends           housing_loan_interest
other_reliefs                paye_withheld                tax_deducted_at_source
quarterly_tax_paid           electronic_donations         pension_contributions
carer_wages                  basic_retirement_pension     state_pension
social_retirement_benefit    taxable_interest             royalty
premium                      annuity                      charges
other_source                 foreign_dividend             foreign_rent
foreign_interest             foreign_other                exempt_interest
global_business_dividends    duty_expenses
```

The income heads follow the return. Each adds to income other than emoluments, so a loss can be set against it.

The four `foreign_` heads hold income from abroad received here, and only a resident may have them. Put income from any other source in `other_source`. `other_income` is its older name and adds to the same total.

The reliefs follow the return. `school_fees` lists the private school fees paid for each child, and each counts up to 60,000. `electronic_donations` counts up to 100,000, `pension_contributions` up to 50,000 and `carer_wages` up to 30,000.

`additional_deduction` is `retired` or `disabled` and adds 50,000. A retired person with emoluments above 50,000 before duty expenses, or with any business, agriculture, private tuition or peer to peer lending, gets nothing.

`housing_loan_interest` is not deducted when your net income, `resident_dividends`, `global_business_dividends` and `exempt_interest` together exceed 4,000,000, or when `spouse_above_interest_bar` is true. Set it to true when your spouse's income, counted the same way, exceeds 4,000,000. `exempt_interest` is interest on savings and fixed deposits, on government securities and on central bank bills. None of the three adds to your income.

`solar_energy`, `rainwater_harvesting` and `fast_charger` each hold `invested` this year and `brought_forward` from earlier years. After every other relief, they are deducted in that order from what income is left, and the rest is carried forward. Only a resident may claim them. When you and your spouse split a solar energy or rainwater harvesting investment, enter your own share as `invested`.

`dependant_income` lists the income of each dependant, in order, as an object with `income`, `exempt` and `emoluments`. `income` is their net income and exempt income together. What is neither exempt nor emoluments adds to your other income, and their emoluments add to yours. A dependant whose income is above 110,000, 80,000, 85,000 or 80,000, for the first to the fourth, cannot be claimed.

Leave out of `income` any state benefit paid to a child or a bedridden relative you claim.

`students` lists each child at a university, as an object with `abroad`, `undergraduate`, `tuition` and `year`. Each gives 500,000, for at most four children and six years. An undergraduate course that is not abroad counts only when the tuition is at least 34,800.

`salary` holds all emoluments. `duty_expenses` holds what you spent wholly, exclusively and necessarily in doing your job, and comes off your emoluments. Include an allowance to the extent it repays such spending.

`other_income` holds income that is neither emoluments, rent nor business. `business` holds the accounts line by line as the return lists them, with an `assets` list for annual allowances.

`rent` holds income from letting, before expenses. `letting` holds what was spent to earn it: `repairs`, `interest`, `syndic_fees`, `other_expenses`, and an `assets` list as in `business`. A rent loss is set against other income and carried forward like a business loss.

`farming` holds agriculture: `gross_income`, `labour`, `rent`, `fertilizers_and_pesticides`, `motor_vehicle_expenses` and `other_expenses`. A loss is treated like a business loss.

`tuition` holds private tuition as `gross_income` and `expenses`. A tuition loss counts as zero.

`lending` holds peer to peer lending as `interest` and `bad_debts`. 80% of the interest is exempt. The bad debts come off the rest. Bad debts above the whole interest are carried forward.

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
it01 change FACTS.json QUESTION KIND    give an answered payment another kind
it01 read DOCUMENT.txt                  propose facts through your endpoint
it01 local DOCUMENT.txt                 propose facts with your model file
it01 rows STATEMENT.txt                 read transactions
it01 credits STATEMENT.txt              label what was paid in
it01 debits STATEMENT.txt               label what was paid out
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
