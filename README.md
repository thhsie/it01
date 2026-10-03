# it01

it01 prepares the income tax of one person on your own computer. A model reads your documents and proposes facts. Python code calculates the tax from the facts that you accept.

- **Readers** read a document and make proposed figures, each with a record of its source.
- **A case file** keeps the data from your documents, your answers and the facts that you accept.
- **Each figure** shows the rule and the section of the law that it comes from.
- **The only connection** goes to the model endpoint that you configure.

A model does not calculate tax. The engine uses a proposed figure only after you accept that figure.

---

## Try it

```sh
git clone https://github.com/thhsie/it01 && cd it01
pip install -e .
echo '{"resident": true, "dependants": 1, "salary": 1200000}' > facts.json
it01 facts.json
```

The command calculates the chargeable income, the income tax, the fair share contribution and the total tax. It also shows the `tax paid`, the `balance of tax` and the `losses carried forward`. Each figure shows its sections of the law, with a link to the page of the law.

## Pay the tax for a quarter

A person with income from rent pays tax for each of the first three quarters of the year.

```sh
echo '{"resident": true, "dependants": 1, "rent": 400000, "period": "quarter"}' > q1.json
it01 q1.json
```

If you do not set `period`, its value is `year`. The tax for a quarter uses the bands for a quarter. A quarter gets one quarter of the deduction for dependants. The engine subtracts the tax deducted at source in that quarter, and a quarter has no fair share contribution.

A statement for each quarter is necessary only above a limit of gross income in the last income year. The engine cannot see that year. Tell the engine with this command:

```sh
it01 answer facts.json "statements of income for each quarter" yes
```

The answer changes no figure. `keep` and the case data then give the due date of the statement for each quarter.

For a quarter, the facts file can have only `resident`, `dependants`, `period`, `rent`, `losses_brought_forward`, `tax_deducted_at_source` and `business`. For each other fact, the engine shows an error that gives the name of the fact. For a quarter, the allowance on an asset is one quarter of the annual allowance. The name of that figure starts with `a quarter of the annual allowance on`.

## Add a document to the case

```sh
export IT01_ENDPOINT=http://localhost:8080/v1/chat/completions IT01_MODEL=your-model
it01 add facts.json bank.txt
it01 keep facts.json
it01 confirm facts.json resident_dividends
```

The endpoint uses OpenAI-compatible chat requests. The endpoint can be on your computer or on a server.

The engine reads a document as text. You can also add a PDF. The engine then reads an image of each page, as a section below shows.

`add` finds the type of the document. A document with a column for the running balance is a bank statement. The engine gives a type to each payment in a statement, through your endpoint or with a model file. The engine reads all other documents with a model file that you supply.

The case keeps the data that the engine reads: each payment in and out with its type, and each figure on a form. Your answers go in `decisions`. The case does not keep the questions. The engine finds the questions each time that it reads the case.

If `documents` has the name of the document that you add, the engine does not read it. The file does not change. The engine also does not read a file with the same contents as a previous file. The name of the file has no effect on this.

The case file does not keep the proposed figures. Each time that the engine reads the case, it calculates them again from the documents and your answers. A payment adds to a fact when `feeds` gives that fact for the type of the payment. Each figure on a form also adds to its fact.

A relief or a business cost also adds to its fact when your answer is yes. A line on a form that you select also adds to its fact. Each figure has a record of its source.

`keep` prints all the data in the case. `confirm` accepts one proposed figure. The figure goes into the facts, and its amount goes into `confirmed`.

If a new document or answer changes an accepted figure, the figure becomes a proposed figure again. `data` then shows the previous amount in `changed`. If no document gives an accepted figure at this time, the engine proposes 0 for that figure.

If a figure comes only from your answers, the engine accepts it when you give the answer. If a new answer or document changes that figure, the accepted figure changes with it. If you answer no, or `forget` or `remove` takes these answers away, the engine removes the figure from the facts. If you use `unconfirm` on that figure, it stays a proposed figure. A figure that you typed with `set` does not change in this way.

`unconfirm` removes an accepted figure from the facts, and the figure becomes a proposed figure again. Use `set` to clear a figure that you gave with `set`.

`data` prints the same case as JSON, with each number as text. Each question has its subject, its words, its answers and its headline. Each question also has your answer, the change in tax for each answer and the fact that closes the question.

Each payment has its type, the type from the reader and your answer. `outside` lists each payment in or out with a date that is not in the income year. Your answers have no effect on this list.

`keep` adds the money paid in for each type, and shows the group of each type. It also adds the money for each group: `income`, `exempt`, `type not known` or `not income`. `data` has the same totals and the group of each type, with the keys `income`, `exempt`, `unsorted` and `other`.

The dates of the payments in a statement show which part of a date is the month. If the first part is from 13 to 31, the day comes first. If the next part is from 13 to 31, the month comes first.

If the dates do not show the sequence, the engine puts no payment from that statement in a month. `keep` lists these payments. The engine reads a year of two digits as `20yy`.

`keep` also adds the money paid in for each month of one income year. The income year starts on 1 July, and the year that `keep` shows has the last payment. `keep` lists each payment with a date that is not in that year. For each month, `data` also gives the total of each group and the payments in each total.

## Remove a document from the case

```sh
it01 remove facts.json statement-march.pdf
```

`remove` removes all the data from one document: its payments, its form figures and its form lines. Your answers about these items also go. Your other answers stay.

The engine then calculates the figures again. If you accepted a figure from that document, the engine proposes that figure again, without the data from that document.

## Type a fact

```sh
it01 set facts.json dependants 2
it01 set facts.json quarterly_tax_paid 12500
it01 set facts.json losses_brought_forward ""
```

`set` writes one fact into the case, with the source `entered by you`. You can set each amount that the engine uses to calculate the tax. For `dependants`, type a number with no decimal part. For `resident` and `spouse_above_interest_bar`, type yes or no.

For `medical_insurance` and `school_fees`, type one amount for each person, with spaces or semicolons between the amounts. A figure that you type replaces the proposed figure.

An empty value clears the fact, but not for `resident`. If the engine cannot calculate the tax with a value, the case does not keep the value.

## Answer a question or correct a figure from a form

```sh
it01 answer facts.json "bank.txt, 1,200.00 paid in on 12/08" rent
```

After the file, type the start of a subject. A subject is a question, a payment or a figure that the engine read from a form. If the start agrees with no subject or with more than one, the command shows an error. The case does not change.

The case keeps the answer in `decisions`, with its subject as the key. If the subject cannot have that answer, the engine shows an error and the case does not change. A new answer replaces the previous answer, and the engine calculates the figures again.

For a payment, the answer is `out` or a type for its direction. You can give this answer for each payment, also for a payment with no question. If its balance keeps a payment out of the totals, the payment counts when you give it a type. For a figure from a form, the answer `wrong` tells the engine that the reader used the incorrect line.

`it01 keep` shows the change in the tax to pay for each answer. The engine calculates this change as if you accept all the proposed figures. If no answer to a question changes the tax, the question shows no change. A question for a missing figure, for example a missing salary, also shows no change.

If an answer is not possible for its question at this time, the answer has no effect. The question then has no answer, and `data` shows the previous answer in `earlier`.

Two statements can have the same payment, with the same direction, date, amount and words. The totals include this payment one time, and the engine shows a question about it. The answer `same` keeps one payment in the totals. A type as the answer adds it as a different payment.

If you remove the other statement, the payment counts again.

`remember` uses your answer for one payment for all payments in the same direction with the same payee words. First, give the payment a type or `out` with `answer`. `keep` then shows `from your answer for` and the rule after the type of each of these payments.

## Fill in the return

```sh
it01 sheet facts.json
```

`sheet` prints the values to type in the return, with one field on each line. The fields are in the same sequence as in the return. Each line gives the field id from the return and the value. `it01/portal.json` is the table that gives the field for each fact.

The return keeps only amounts with no decimal part, and it removes the decimal part when you type. Thus the sheet gives each amount with no decimal part. The last lines are the totals that the return calculates from these amounts. Use them to check the return after you type.

Some lines end with `the return fills in this field, examine it`. The return puts a value in these fields. Make sure that each figure agrees with your document.

A line that ends with `the total of all rows` is for a table with one row for each employer or payer. Divide the total between the rows, as your documents show.

The last lines, in the `not on the sheet` section, list the facts that have no field of their own. Each line tells you where to type the fact. For a quarter, `sheet` shows an error, because the return is for a year.

## Remove an answer

```sh
it01 forget facts.json "bank.txt, 1,200.00 paid in on 12/08"
```

`forget` removes your answer for one subject. A payment gets the type from the reader again. A figure from a form counts again, and a question has no answer again. If this changes a figure that you accepted, that figure becomes a proposed figure again.

## Read with your own model file

```sh
pip install -e '.[local]'
export IT01_MODEL_FILE=reader.onnx IT01_TOKENISER=tokenizer.json
it01 local statement.txt
```

The `local` command uses an encoder that gives a score to each sequence of words. The encoder reads the document one time, and each answer refers to a position in the text. The engine gives the model one form to complete. When the model gives two possible results, the totals on the form select the correct result.

`it01/model.json` gives the names that your file uses for the nine inputs and outputs of the package. It also gives the words that the file must get. `it01/reading.json` has the form, and the instruction that the endpoint reader sends.

The `title` of the form is the heading that a document must have, to be that form. `it01 add` shows an error if a document is not a bank statement and does not have that heading.

The `ends` key of the form finds the last month of the income year of the document. If the case has an income year, `add` does not read a document for a different year. It also does not read a document if the engine cannot find its year. The two keys are optional.

## Read a PDF from the images of its pages

```sh
pip install -e '.[pdf,local]'
export IT01_DETECTOR=detector.onnx IT01_RECOGNISER=recogniser.onnx
it01 rows statement.pdf
```

The engine makes an image of each page of a PDF and reads the image with two model files. The engine does not use the text layer. Thus a scan and a file from a computer give the same result. If the engine finds no text on a page, it shows an error that gives the page number.

The detector gets the page with no side more than 1280 pixels, and each side is a multiple of 32. For each pixel, the detector gives the probability that the pixel is part of a line of text.

The recogniser gets one line with a height of 48 pixels. For each step, it gives the probability of each character. The first character is no character, and the last character is a space.

The metadata of the recogniser lists its characters in `character`, one character on each line. If the list does not agree with the output, the engine shows an error. The two files get the red, green and blue channels first, with values from minus one to one.

## Read a bank statement

```sh
it01 rows statement.txt
it01 credits statement.txt
it01 debits statement.txt
```

`rows` finds the columns from the arithmetic, and it compares each balance with the running total. It marks each transaction `ok`, `does not agree` or `not checked`. Each transaction starts with the number of its line in the document, from 1, as `it01 show` prints it. For each page, `rows` gives the number of amounts that the engine did not use.

A statement gives its currency when a code of three characters comes after the word currency, above the first transaction. `it01 add` keeps that code with the document. If the case has a statement in a different currency, `add` does not read the new statement.

`credits` gives a type to each payment in, through your endpoint. If you set `IT01_LABELLER`, it uses your model file. The types are in `it01/labelling.json`. `feeds` gives the fact that each type adds to, and `asking` gives the types that make a question for you.

`not_income` gives the types that are not income. Each type must be in one of `feeds`, `needs`, `exempt`, `asking`, `not_income` or `business`.

`debits` gives a type to each payment out, with the types in `it01/paying.json`. It prints the total of each type. Most types are for a relief in the law, for example a pension contribution or school fees. The type of a payment out does not propose a fact.

For each type of payment out in a statement, `it01 add` makes one question. `claims` gives the types that add to a fact when the answer is yes, with the condition from the law.

`certificates` gives the types that get their figure from a certificate. For each type, it gives the question and the fact for that figure. The question closes when the case has that fact.

`business` gives the types that make a question only when the case has business income. The answer yes adds the total to the line of the accounts that `business` gives. An amount as the answer adds only that amount.

`aside` gives the types that do not count. If the balance after a payment does not agree, the totals do not include that payment.

`unsure` gives the types from `aside` that can include a payment for a claim. For each statement, one question lists those payments. The person selects each payment for a claim, and each selected payment gets its own question. The other payments get the type that `personal` gives. A statement with one such payment gets one question for the type of that payment.

`keep` shows the answers to each question after a colon, and each answer tells its effect.

A question for a missing document, for example a statement of emoluments, closes when the case has the figure. Its answers give a different type for the money, for example business or rent. The answer changes the type of each payment of that type. The engine then proposes their total in the income year as the fact for the new type.

For a question about a payment in, give one of the types that `it01 keep` lists after the question.

A question about business costs lists its payments with numbers. The answer is yes, no, the business part as an amount, or the numbers of the business payments. For example, type `payments 1, 3`. The engine adds these payments and keeps the total.

The case keeps payments that can be business costs, also when the case has no business income. Then each statement has one question about these payments. If you answer `business`, each type of cost gets a question, also when the business has no income. If you answer `not`, the costs in that statement get no questions.

When the case has business income as a fact or a proposed figure, the costs in previous statements get questions.

## Give types to payments in with your own model file

```sh
export IT01_LABELLER=labeller.onnx IT01_TOKENISER=tokenizer.json
it01 credits bank.txt
```

If you set `IT01_LABELLER`, a classifier on this computer gives the type of each credit. The engine does not use the endpoint. The file gives a score to each type in `it01/labelling.json`, for one credit at a time. The type with the maximum score is the result.

Each input of the file has one length for all credits, or a length that can change. If the length can change, the file reads each credit at its own length.

`it01/labeller.json` gives the names that your file uses for its four inputs and its output. It also gives the marks and words around each type and example. The task name, the instruction and the layout of one credit are in `model` in `it01/labelling.json`. The types, their descriptions and the examples are also in that file.

The labeller uses the same `IT01_TOKENISER` as the reader. `debits` uses the same model file. The task, the instruction, the layout of the line and the types are in `it01/paying.json`.

The metadata of the file lists its tasks in `tasks`, with commas between them. For the two tables, the value is `source,purpose`. If the file does not list the task of a table, the engine shows an error.

## The facts file

The file must have `resident`, and all other facts are optional. `dependants` is a number of persons, and `business` is an object.

`medical_insurance` is a list of premiums, with one premium for each person with insurance. Your premium is first, then the premium of each dependant in sequence. The list has a maximum of five premiums, for you and four dependants.

The other facts are amounts. Write each amount as a number with a maximum of two digits after the decimal point.

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

The income heads are the same as in the return. Each head adds to income other than emoluments. Thus you can set a loss against that income.

The four `foreign_` heads are for income from a different country that you received here. Only a resident can have them. Put income from all other sources in `other_source`. `other_income` is the previous name of this fact, and it adds to the same total.

The reliefs are the same as in the return. `school_fees` lists the fees that you paid to a private school for each child. Each amount counts up to 60,000. `electronic_donations` counts up to 100,000, `pension_contributions` up to 50,000 and `carer_wages` up to 30,000.

`additional_deduction` is `retired` or `disabled` and adds 50,000. A retired person gets no deduction if the emoluments before duty expenses are more than 50,000. A retired person with business, agriculture, private tuition or peer to peer lending also gets no deduction.

The engine does not deduct `housing_loan_interest` if the total of these amounts is more than 4,000,000: your net income, `resident_dividends`, `global_business_dividends` and `exempt_interest`. It also does not deduct the interest if `spouse_above_interest_bar` is `true`. Set it to `true` if the same total for your spouse is more than 4,000,000.

`exempt_interest` is interest on savings and fixed deposits, on government securities and on central bank bills. The three amounts do not add to your income.

`solar_energy`, `rainwater_harvesting` and `fast_charger` each have `invested`, for this year, and `brought_forward`, from previous years. The engine deducts them after all other reliefs, in that sequence, from the remaining income. The remaining amount goes forward to the next year.

Only a resident can claim them. If you and your spouse share an investment in solar energy or rainwater harvesting, type your part as `invested`.

`dependant_income` lists the income of each dependant in sequence, as an object with `income`, `exempt` and `emoluments`. `income` is the total of the net income and the exempt income of the dependant.

The income that is not exempt and not emoluments adds to your other income. The emoluments of the dependant add to your emoluments. You cannot claim a dependant with income above 110,000, 80,000, 85,000 or 80,000, for dependants 1, 2, 3 and 4.

Do not include in `income` a benefit from the government for a child or a bedridden relative that you claim.

`students` lists each child at a university, as an object with `abroad`, `undergraduate`, `tuition` and `year`. Each child gives 500,000, for a maximum of four children and six years. An undergraduate course in the country counts only if the tuition is a minimum of 34,800.

`salary` has all emoluments.

`duty_expenses` is the money for your job that the law lets you deduct. The law accepts only money that you used "wholly, exclusively and necessarily" to do your job. The engine deducts it from your emoluments. Include the part of an allowance that pays back this money.

`other_income` has income that is not emoluments, rent or business. `business` has the accounts line by line, in the sequence of the return. Its `assets` list is for annual allowances.

`rent` has the income from rent, before expenses. `letting` has the expenses for that income: `repairs`, `interest`, `syndic_fees`, `other_expenses`, and an `assets` list as in `business`. The engine sets a rent loss against other income, the same as a business loss. The remaining loss goes forward to the next year.

`farming` has the income and expenses of agriculture: `gross_income`, `labour`, `rent`, `fertilizers_and_pesticides`, `motor_vehicle_expenses` and `other_expenses`. The engine uses a loss from agriculture the same as a business loss.

`tuition` has private tuition as `gross_income` and `expenses`. A tuition loss counts as zero.

`lending` has peer to peer lending as `interest` and `bad_debts`. 80% of the interest is exempt. The engine deducts the bad debts from the remaining interest. If the bad debts are more than all the interest, the remaining bad debts go forward to the next year.

The engine removes nine keys from the facts before it calculates the tax:

```
version year sources confirmed documents payments readings lines decisions
```

`documents` has each document that the engine read. Each document has its type, the full path of the file and a mark of its contents. A bank statement also has its currency. A form also has the last month of its income year.

`payments` has each payment in and out of a statement. Each payment has its document, direction, amount, date, description, type, balance check, month, and the number of its line from 1, as `it01 show` prints it. If the balance after a payment did not agree, the payment gives no figure until you give it a type. A figure shows the number of its payments with no balance check.

`readings` has each figure that the engine read from a form, with its line. `lines` has each line of a form that the reader was not sure of, with the possible lines. `decisions` has your answers, with the subject as the key.

The engine cannot read a case of a different `version`. `it01 rebuild` reads each document again from its path. It keeps your facts, their sources and all your answers.

`rebuild` removes each answer for a subject that the documents do not give, and lists these answers. `rebuild` can also read a case of a previous version, but it cannot keep the answers of that case. The case does not change if it does not show the location of a document. It also does not change if a document is not at its location.

`year` has the income year of the case, as its first and last month. The income year starts in July and has twelve months. `it01 year` sets it. If a form is for a different income year, `it01 year` shows an error.

The months of money paid in are the months of that income year. A payment with a date that is not in the income year gives no figure and no question. `keep` lists it. A payment with a month that is not clear stays in the totals.

`it01 show` prints a document from the path in the case. It shows an error if the file is not at that path. It also shows an error if the file changed after the engine read it.

## Keep your own copies

The package has default copies of `it01/model.json`, `it01/reading.json` and `it01/labelling.json`, and you can change them. Set `IT01_DATA` to your own folder. The engine then uses each file in that folder, not the file in the package. For each file that is not in your folder, the engine uses the file in the package.

```sh
mkdir -p ~/it01
cp "$(python -c 'import it01, pathlib; print(pathlib.Path(it01.__file__).parent)')/model.json" ~/it01/
export IT01_DATA=~/it01
```

If the folder is not there, the engine shows an error.

## Commands

```
it01 FACTS.json                         calculate the tax
it01 add FACTS.json DOCUMENT.txt        read a document into the file
it01 keep FACTS.json                    print all the data in the case
it01 show FACTS.json DOCUMENT.txt       print a document as the engine read it
it01 confirm FACTS.json FACT            accept a proposed figure
it01 answer FACTS.json SUBJECT ANSWER   answer a question, give a type to a payment, or mark a form figure as incorrect
it01 remember FACTS.json PAYMENT        use the answer for one payment for all payments with the same words
it01 forget FACTS.json SUBJECT          remove your answer for a subject
it01 year FACTS.json YYYY-MM            set the income year from its first month
it01 set FACTS.json FACT VALUE          type a fact, or clear it with an empty value
it01 rebuild FACTS.json                 read all the documents again
it01 remove FACTS.json DOCUMENT         remove a document from the case
it01 unconfirm FACTS.json FACT          make an accepted figure a proposed figure again
it01 read DOCUMENT.txt                  propose facts through your endpoint
it01 local DOCUMENT.txt                 propose facts with your model file
it01 rows STATEMENT.txt                 read the payments
it01 credits STATEMENT.txt              give a type to each payment in
it01 debits STATEMENT.txt               give a type to each payment out
it01 data FACTS.json                    print all the case as JSON
it01 sheet FACTS.json                   print what to type in the return
```

`IT01_KEY` is a bearer token for an endpoint that must have one. `IT01_TIMEOUT` is the number of seconds to wait for the endpoint. `IT01_DEBUG=2` prints the reply from the endpoint. `IT01_DATA` is a folder with your own copies of the JSON files in `it01/`.

## Cases that the engine does not calculate

The endpoint reader does not read the business accounts or the number of dependants. The engine does not calculate the business accounts when part of the business is exempt. It does not calculate the deductions for special categories of employees, or the deduction for artists. It does not calculate a balancing charge for the sale of an asset.

The engine has no fact for dividends that a body of yours received and did not pay out. The fair share contribution counts these dividends as your dividends.

## Run the checks

```sh
pip install -e '.[linting]'
python -m ruff check . && python -m mypy && python -m unittest && MAX_LINE_COUNT=3000 python sz.py
```

Run all the checks before a commit, and make sure that they show no errors. The repository has no formatter. Do not use a formatter.

## Send a change

You can send corrections and updates to the tax rules. Read [AGENTS.md](AGENTS.md) first, because its rules apply to each change.

Do not remove line breaks only to decrease the line count. The repository uses the line count as a measure of complexity. When you remove a line break, the code does not become more easy to read.

Each bug correction must include a test that shows the bug without the correction. A refactor is a pull request of its own, and it does not change a calculated result. In the pull request, explain your change in one or two lines.

## License

MIT
