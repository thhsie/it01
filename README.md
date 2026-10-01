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

The case keeps what it reads: every payment in and out with its label, and each figure a form shows. What you say about them is kept under `decisions`. Questions are not kept. The open questions are worked out each time the case is read.

A document whose name is already in `documents` is not read at all, and the file is left alone. A file identical to one read before is refused the same way, whatever it is called.

The proposed figures are not kept in the file. Each time the case is read, they are worked out from what was read and what you said. Each payment labelled with a kind that feeds a fact adds to it, and so does each figure a form shows.

A relief or business cost you answered yes to, and a form line you chose, add too. Each figure notes where it came from.

`keep` prints everything processed so far. `confirm` moves one figure into the facts, and keeps the amount in `confirmed`. When a later document or answer changes that figure, it is proposed again, and `data` lists its old amount under `changed`. A confirmed figure no longer read from any document is proposed at 0.

`unconfirm` takes a confirmed figure out of the facts, and it is proposed again. A figure you entered is cleared with `set`.

`data` prints the same case as JSON, with every number as text. Each question comes with its subject, wording, answers, headline and price, and what you said. Each payment comes with its label, the label it was read with, and what you said.

`keep` also adds up the money paid in by the kind it was labelled, and names the group of each kind. It also sums it by group: income, exempt, still to sort, or not income. `data` carries the same totals and the group of each kind.

The dates of a statement's labelled payments say which part is the month. A first part from 13 to 31 means the day comes first, and a second part from 13 to 31 means the month comes first. When the dates do not show the order, no payment from that statement is placed in a month, and `keep` lists them. A two-digit year is read as 20yy.

Money paid in is also added up for each month of one income year. The Act's year starts on 1 July, and the year shown holds the latest payment. A payment dated before that year is listed. `data` also gives, for each month, its sums by group and the labels in each sum.

## Take a document out

```sh
it01 remove facts.json statement-march.pdf
```

`remove` drops everything read from one document: its payments, form figures and form lines. What you said about them goes too. Other answers stay.

The figures are worked out again, so a figure you confirmed from that document is proposed again without it.

## Enter a fact yourself

```sh
it01 set facts.json dependants 2
it01 set facts.json quarterly_tax_paid 12500
it01 set facts.json losses_brought_forward ""
```

`set` writes one fact into the case, with the source `entered by you`. It takes any amount the computation reads, a whole number of `dependants`, and yes or no for `resident` and `spouse_above_interest_bar`. A figure entered this way replaces its proposal.

An empty value clears the fact, except `resident`. A value the computation would refuse is not kept.

## Answer a question or correct a reading

```sh
it01 answer facts.json "bank.txt, 1,200.00 paid in on 12/08" rent
```

Give the start of a subject after the file. A subject is a question, a payment, or a figure a form was read as. When it matches none, or more than one, nothing changes and the command says so.

The answer is kept under `decisions`, keyed by its subject. An answer the subject does not take is refused, and the case is left as it was. Answering again replaces the earlier answer, and the figures are worked out again.

A payment takes `out`, or any kind of its statement, even one the labeller was sure of. A payment left out for its balance counts once given a kind. A form figure takes `wrong` when the reader took the wrong line.

`it01 keep` prints what each answer would change in the tax to pay. The change is worked out from the figures the case would hold with every proposal confirmed. A question whose answers all leave the tax as it is shows no change.

An answer that no longer fits its question counts for nothing, and the question opens again. `data` shows that answer under `earlier`.

A payment with the same direction, date, amount and wording as one in an earlier statement is counted once. It is asked about, because two statements can overlap. `same` keeps it counted once, and a kind counts it as another payment. A payment counts again once the statement it repeats is removed.

## Fill in the return

```sh
it01 sheet facts.json
```

This prints what to type in the return, one field a line, in the order the return asks for them. Each line gives the return's own field id and the value. The table that maps facts to fields is `it01/portal.json`.

The last lines are the return's own totals, so you can check them after typing. The return keeps whole amounts and drops the fraction as you type.

Some lines end with `filled in by the return, check it`. The return fills those fields itself. Check that each figure matches your document.

A line ending with `the total of all rows` belongs to a table with one row per employer or payer. Split it across the rows as your documents do.

Facts the return has no single field for are listed last, with where to enter them. The sheet refuses a quarter, because the return takes a year.

## Take an answer back

```sh
it01 forget facts.json "bank.txt, 1,200.00 paid in on 12/08"
```

`forget` removes what you said about one subject. A payment goes back to the label it was read with, a form figure counts again, and a question opens again. When this moves a figure you confirmed, that figure is proposed again.

## Read with a model file of your own

```sh
pip install -e '.[local]'
export IT01_MODEL_FILE=reader.onnx IT01_TOKENISER=tokenizer.json
it01 local statement.txt
```

The `local` command takes an encoder that scores runs of words. It reads the document once and every answer points at a place in the text. The model is asked to fill one form, and the form's own sums decide between competing readings.

`it01/model.json` says what your file calls the nine things the package needs, along with the wording it expects. `it01/reading.json` holds the form, and the instruction the endpoint reader sends.

The form's `title` is the heading a document must print to be read as that form. `it01 add` refuses a document that is neither a bank statement nor titled.

The form's `ends` finds the last month of the income year the document covers. When the case has a year, a document for another year is refused, and so is one whose year cannot be read. Both keys are optional.

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

A statement names its currency when a three-letter code follows the word currency above its first transaction. `it01 add` keeps that code with the document. It refuses a statement whose currency differs from one the case already holds.

`credits` labels every payment in through your endpoint, or your model file when `IT01_LABELLER` is set. The kinds are in `it01/labelling.json`. `feeds` says which fact each kind adds to, and `asking` says which kinds it asks you about.

`not_income` names the kinds that are not income. Every kind must be fed, needed, exempt, asked about or not income.

`debits` labels every payment out the same way, with the kinds in `it01/paying.json`, and prints the total of each kind. Most kinds match a relief in the law, such as a pension contribution or school fees. A label proposes no fact.

`it01 add` asks one question for each kind of payment out in a statement. `claims` names the kinds a yes adds to a fact, with the condition the law sets. `certificates` names the kinds whose figure comes from a certificate, and asks for it.

`business` names the kinds asked about only when the case has business income. A yes adds the total to the accounts line it names, and a typed amount adds only that part. `aside` names the kinds that count for nothing. A payment whose balance does not agree is left out of the totals.

A question about money paid out, a missing statement or a balance that does not agree lists its answers after a colon. Each answer says what it does.

A question about a missing statement closes once the figure is known. Its answers say what the money was instead, such as business or rent. The answer relabels every payment of that kind. It proposes their total within the year under the fact for the new kind.

A question about a payment in takes one of the kinds `it01 keep` lists after it.

A question about business costs paid out lists its payments by number. It takes yes, no, the business part as an amount, or the payments that were business costs, such as `payments 1, 3`. The engine adds up the payments named and keeps the sum.

Payments that look like business costs are kept even when the case has no business income. Each statement then asks once whether they are costs of your business. Answer business and each kind of cost is asked about, even with no business income yet. Answer not and that statement's costs are never asked about.

Once business income is given or proposed, the costs kept from earlier statements are asked about too.

## Label bank credits with a model file of your own

```sh
export IT01_LABELLER=labeller.onnx IT01_TOKENISER=tokenizer.json
it01 credits bank.txt
```

With `IT01_LABELLER` set, each credit is labelled by a classifier on this computer and the endpoint is not called. The file scores every kind in `it01/labelling.json` for one credit at a time, and the highest score wins.

`it01/labeller.json` says what your file calls its four inputs and its output, and the marks and wording around each kind and example. The task name, the instruction and the layout of one credit are under `model` in `it01/labelling.json`. The kinds, their descriptions and the examples are there too. The labeller reads with the same `IT01_TOKENISER` as the reader.

`debits` reads with the same model file. The task, the instruction, the line layout and the kinds are in `it01/paying.json`.

The file lists the tasks it was trained for in its metadata, under `tasks`, separated by commas: `source,purpose` for both tables. A file that does not list a table's task is refused.

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

Nine keys are set aside before the computation, and none of them reaches it:

```
version year sources confirmed documents payments readings lines decisions
```

`documents` holds each document read, with its kind, the full path it was read from and a mark of its contents. A bank statement also holds its currency. A form holds the last month of the year it covers.

`payments` holds every payment in and out of a statement. Each has its document, direction, amount, date, description, label, balance check and month. A payment whose balance did not agree gives no figure until you give it a kind. A figure notes how many of its payments were not checked.

`readings` holds each figure a form was read as, with the line it came from. `lines` holds each line of a form the reader asked about, with the lines it could be. `decisions` holds what you said, keyed by its subject.

A case of another `version` is refused. `it01 rebuild` reads every document again from its path. It keeps the facts you gave, their sources and everything you said.

`rebuild` drops what you said about a subject that is no longer read, and lists it. It also reads a case of an earlier version, whose answers it cannot keep. Nothing changes if a document has no recorded path or is no longer there.

`year` holds the income year the case covers, as its first and last month. It starts in July and runs twelve months. `it01 year` sets it. A new year is refused when a form covers another year.

The months of money paid in follow the year. A bank statement line dated outside the year gives no figure and no question, and `keep` lists it. A line whose month cannot be read stays in.

`it01 show` prints a document from its recorded path. It refuses one that is no longer there, and one whose file has changed since it was read.

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
it01 answer FACTS.json SUBJECT ANSWER   answer a question, relabel a payment, or mark a reading misread
it01 forget FACTS.json SUBJECT          take back what you said about a subject
it01 year FACTS.json YYYY-MM            set the income year from its first month
it01 set FACTS.json FACT VALUE          enter a fact yourself, or clear it with an empty value
it01 rebuild FACTS.json                 read every document again
it01 remove FACTS.json DOCUMENT         take a document out of the case
it01 unconfirm FACTS.json FACT          take back a confirmed figure
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
