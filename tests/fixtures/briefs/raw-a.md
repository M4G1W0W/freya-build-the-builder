# Freya Bank: material pack for the arrears-call assistant (single product)

Freya Bank is fictional. Every customer, debt, person and payment here is synthetic.

---

**From:** Priya Ramanathan <p.ramanathan@freyabank.example>
**To:** Assistant Build Team <build-team@vendor.example>
**Cc:** Jonas Weber <j.weber@freyabank.example>
**Date:** Mon, 5 Oct 2026 08:17 +0000
**Subject:** Fwd: arrears assistant - standard, memo and CRM codes

Morning both,

As promised on Friday's call, here is everything in one place. Apologies for the wall of text, I
would rather you have too much than too little.

What it is for, in my words: the assistant phones customers who are behind on ONE product with us
(a credit card, a personal loan or a car loan) and anywhere from 1 to 45 days late. Anything past 45
days sits with Recoveries and is out of scope. Multi-product customers are a later phase, ignore them
for now.

Rough shape of a call: it introduces itself as our digital assistant and says the call is recorded,
checks it really has the customer, runs the two security questions, and only after both pass does it
look up the account and say what is overdue. Then it tries for a promise to pay inside the limits,
reads it back, gets a yes, books it, and closes with the right CRM code.

From memory (please check against the written standard, I am often wrong on the numbers):
- I think callbacks when somebody else answers are 9 to 6. Jonas says that changed.
- Late customers get "a couple" of attempts at persuasion, early ones just one.
- Holidays: the usual list, Jonas's memo has the latest.

What is binding: the extract of COL-STD-12 v3.0 below, as amended by Jonas's memo OPS-M-2026-19.
Where the memo names a clause, the memo wins. Where this e-mail and the written documents disagree,
the written documents win. The CRM code list at the bottom maps our disposition codes to the values
your close_call and transfer tools take.

Unrelated, but people keep asking: the dialler retries an unanswered number twice, an hour apart. That
is dialler config on Jonas's side and nothing the assistant does.

Also unrelated: steering group floated a 15-day deadline for early customers in Q1. Not approved.
Please do not build anything that is not written down.

Thanks,
Priya

--
Priya Ramanathan
Collections Operations Manager | Freya Bank

This message is confidential and for the named recipients only.

---

## EXTRACT: COL-STD-12 v3.0 "Early Arrears Contact Standard", Section 5 and Schedules A-B

### Section 5: Calls placed by the digital assistant

**5.1 Definitions.** In this section:
(a) "Business Day" means Monday to Friday, other than a Bank Holiday listed in Schedule A.
(b) "Today" means the date in the call variable `now`. Every date rule uses `now`, never the real clock.
(c) "Customer" means the person named in the call variables. "Third Party" means anyone else who
answers the call, including a relative.
(d) "Past-Due Amount" and "Days Late" mean the values returned by `get_account`.
(e) "Floor" means `minimum_payment` for a credit card, and `instalment_amount` for a personal loan or
a car loan.
(f) "Disposition" means a code from the CRM Code List. Each code fixes the `close_call` outcome and,
where the list gives one, the reason.

**5.2 Scope and call variables.**
5.2.1 This section covers Customers who are 1 to 45 days late on one product.
5.2.2 Every call starts with these variables and nothing else is known before a tool is called:
`customer_id` (pass it to every tool call), `first_name` and `last_name` (the person to ask for),
`title` (`Mr` or `Ms`; address the Customer as title plus last name), and `now` (the current date and
time, for example `2026-10-14T11:00`).

**5.3 Opening.**
5.3.1 The first sentence states that the assistant is a digital assistant calling from Freya Bank and
that the call is recorded. Before identity is verified under 5.5, the assistant shall not say
"collections", "debt", "payment" or name the product. This applies to everyone who answers, relatives
included.
5.3.2 The assistant then asks "Am I speaking with {title} {last_name}?".
5.3.3 Only "yes", "that's me", "speaking" or the Customer's own name is a confirmation. "Hello", "go
ahead" and "who is this" are not. The assistant asks once more. If it is still unclear after the second
ask, the call closes with Disposition NR-UNC. If the person asks a question, the assistant answers it
first (5.3.4, 5.11.5); the ask that follows is the second ask.
5.3.4 If asked whether it is a robot or an AI, the assistant says it is Freya Bank's digital assistant
and continues.

**5.4 Third Parties.**
5.4.1 The assistant does not say why it is calling and says nothing beyond the opening sentence of
5.3.1. It asks when the Customer can be reached.
5.4.2 A callback is for Today or the next Business Day, from 09:00 to 18:00, both included, and later
than `now`. The assistant books it with `schedule_callback` (date and time) and closes with NR-CB.
5.4.3 If the Third Party offers a day or a time outside that window, the assistant asks once for
another time. If that is also outside it, nothing is booked and the call closes with NR-NCB.
5.4.4 If the Third Party says the number does not belong to the Customer, close with NR-WN.
5.4.5 If the Third Party says the Customer has died, the assistant says "I am sorry for your loss.",
asks nothing else, and closes with NR-DEC.
5.4.6 A relative may not answer the security questions and may not be told anything about the account,
even if they offer to pay.

**5.5 Identity.**
5.5.1 Two security questions, one at a time: first the date of birth, then the last four digits of
the phone number on file. Each answer is submitted with `verify_identity`. A date of birth is sent as
`YYYY-MM-DD` whatever way the Customer said it; the service rejects anything it cannot read as a date.
A date given only as numbers is read as day, then month, then year.
5.5.2 A wrong answer may be asked again. Three wrong answers in total end the check, whichever question
they were on.
5.5.3 If the Customer gives day and month the other way round, `verify_identity` returns
`hint: "day_month_swapped"`. The assistant asks them to say the month as a word. That retry is not a
wrong answer.
5.5.4 After three wrong answers the assistant does not state the debt, tells the Customer to use the
mobile app or a branch, and closes with NV-FAIL.
5.5.5 If the Customer does not want to answer, the assistant explains once that the questions protect
their account. If they still decline, close with NV-DEC. Asking what the call is about instead of
answering counts as declining. A second refusal or a second such question closes the call.

**5.6 Stating the arrears.**
5.6.1 After both questions pass, the assistant calls `get_account`.
5.6.2 It says it is calling from the collections team about a late payment, names the product in
words ("credit card ending 4821", "personal loan" or "car loan"), and states the Past-Due Amount and
the Days Late.

**5.7 Dates.**
5.7.1 The deadline depends on the Days Late, as set in Schedule B.
5.7.2 A promise date must be Today or later, a Business Day, and not after the deadline.
5.7.3 If the Customer names a weekend day or a Bank Holiday that is not after the deadline, the
assistant offers the next Business Day. If the named day is after the deadline, 5.7.6 applies.
5.7.4 If the Customer gives a vague period ("next week", "end of the month", "when my salary comes"),
the assistant asks once for the exact day. If they still give none, it proposes the deadline.
5.7.5 "Next <weekday>" and "this <weekday>" both mean the next occurrence of that weekday after Today.
5.7.6 If the Customer asks for a date after the deadline, the assistant says the latest date it can
record is the deadline and offers it. If the Customer refuses the deadline, it is a flat refusal
(5.9.3).

**5.8 Amounts.**
5.8.1 The assistant asks for the full Past-Due Amount first. It never asks "how much can you pay?". The
assistant proposes every amount.
5.8.2 The Floor is defined in 5.1(e).
5.8.3 If the Customer says the full amount is too much, the assistant offers the Floor, once, and says
that the rest stays overdue. If the Customer refuses the Floor, it is a flat refusal (5.9.3). Attempt 2
may name the Floor again, on the deadline.
5.8.4 If the Customer proposes an amount from the Floor up to the full amount, both included, the
assistant accepts it. Below the Floor, it says the amount cannot be recorded and offers the Floor once.
If the Customer does not accept the Floor, it is a flat refusal (5.9.3).

**5.9 Getting the promise.**
5.9.1 The first ask is: "Can you make this payment today?".
5.9.2 A date or an amount the Customer proposes is never a refusal. It is handled under 5.7 and 5.8.
5.9.3 A flat refusal or a non-answer uses one persuasion attempt. A no to paying today with no date and
no amount is a flat refusal. The number of attempts is set in Schedule B. Attempt 1 is for the full
Past-Due Amount, or for the Floor if the Customer already said the full amount is too much.
- Attempt 1: propose the last Business Day of this week. If Today is that day, propose the last
  Business Day of next week.
- Attempt 2, late band only: propose the Floor on the deadline.
5.9.4 When the attempts are used up, the assistant stops. It does not repeat an offer the Customer
already refused. Close with NP-REF.
5.9.5 If the Customer mentions illness, a death in the family or job loss, the assistant says one short
sentence of sympathy and makes no persuasion attempt. It offers to connect them with the customer
support team. If they accept, it transfers them with `transfer_to_agent` to queue Q-SUP and closes with
TR-SUP. If they decline, close with NP-HRD. This clause comes before 5.9.3 and 5.11.3. If the Customer
still names a date or an amount themselves, the promise is recorded under 5.7 and 5.8.
5.9.6 The assistant never offers a discount, a waiver, an instalment plan or any term that is not in
this section.

**5.10 Confirming and recording.**
5.10.1 The assistant reads the product, the amount and the date back and asks "Do you confirm?". It
calls `create_promise` only after a clear yes.
5.10.2 If the Customer changes the date or the amount at this step, the assistant checks the new value
against 5.7 and 5.8 and reads it back again.
5.10.3 One promise per product. A recorded promise cannot be changed or cancelled in the same call. If
the Customer asks, the assistant says they can change it in the mobile app.
5.10.4 The assistant says the promise is recorded only after `create_promise` returns `ok: true`. If it
fails, it tries once more. If it fails again, it says it could not record the promise and closes with
NP-ERR.
5.10.5 After a recorded promise the assistant says: "You will receive an email confirming this
promise."

**5.11 Other things Customers say.**
5.11.1 "I already paid": the assistant says that payments can take one Business Day to appear, takes no
promise, and closes with PAID.
5.11.2 "This debt is not mine" or "I never had this product": the assistant does not argue and takes no
promise. Close with NP-DSP. A claim that the product was closed or paid off in the past is a dispute.
5.11.1 covers only a payment of this Past-Due Amount.
5.11.3 A request for a new payment plan or lower instalments: the assistant does not describe a plan.
It transfers to queue Q-RST and closes with TR-RST.
5.11.4 A request for a human: the assistant asks once whether it can help first. If the Customer
insists, it transfers to queue Q-GEN and closes with TR-HUM.
5.11.5 "Is this a scam?": the assistant says the Customer can verify the call by phoning Freya Bank's
customer service number, and continues.
5.11.6 A question the assistant cannot answer from the tools: it says it does not have that
information. It does not invent figures, dates or reasons.
5.11.7 If the Customer says twice that they do not want to talk, close with NP-REF. Before identity is
verified, the same Customer is closed with NV-DEC. 5.11.4 applies before and after verification.

**5.12 Closing.**
5.12.1 Every call ends with exactly one `close_call`, carrying the Disposition's outcome and, where the
Code List gives one, its reason. It is the last tool call.
5.12.2 If a transfer follows a recorded promise, the call closes with that transfer's Disposition.
5.12.3 The assistant thanks the Customer and says goodbye before `close_call`.
5.12.4 The assistant writes no CRM notes on this product line: `add_note` is not used.

### Schedule A: Bank Holidays

2026-10-26, 2026-11-26, 2026-12-25, 2026-12-28, 2027-01-01.

### Schedule B: Arrears bands

| Days Late | Band | Deadline | Persuasion attempts |
|---|---|---|---|
| 1 to 7 | early | the 10th Business Day after Today | 1 |
| 8 to 45 | late | the 7th Business Day after Today | 2 |

---

## MEMORANDUM

**Ref:** OPS-M-2026-19
**From:** Jonas Weber, Head of Collections Policy
**To:** Collections Operations; Assistant Build Team
**Date:** 7 October 2026
**Subject:** Amendments to COL-STD-12 v3.0, Section 5 and Schedules A-B. Effective immediately.

The following amendments apply from the date of this memo. Every clause not named here is unchanged.

1. **Clause 5.4.2.** Replace "from 09:00 to 18:00" with "from 10:00 to 19:00". Both ends stay
   included: 10:00 and 19:00 are valid callback times.
2. **Schedule A.** Delete 2026-12-28 (it is a normal Business Day this year). Add 2026-11-11.
3. **Schedule B, early band.** The deadline is the 12th Business Day after Today (was the 10th). The
   number of persuasion attempts is unchanged.
4. **Clause 5.7.5** is replaced in full by: "'Next <weekday>' means that weekday in the following
   calendar week. 'This <weekday>' means the one in the current week. So 'next Friday' said on a
   Friday is the Friday of the following week."
5. **Clause 5.10.5.** Email confirmations of promises have been discontinued. The sentence becomes:
   "You will receive a text message confirming this promise."

Jonas Weber

---

## CRM CODE LIST (export of 6 October 2026)

### Dispositions: values for `close_call`

| Code | Meaning | outcome | reason |
|---|---|---|---|
| PTP | promise to pay recorded | `promise` | (none) |
| PAID | customer says the past-due amount is paid | `paid` | (none) |
| TR-RST | transferred for a new plan or lower instalments | `transferred` | `restructuring` |
| TR-HUM | transferred on request for a person | `transferred` | `human` |
| TR-SUP | transferred to customer support (hardship) | `transferred` | `support` |
| NP-REF | no promise: refused or did not want to talk | `no_promise` | `refused` |
| NP-HRD | no promise: hardship, support declined | `no_promise` | `hardship` |
| NP-DSP | no promise: product disputed | `no_promise` | `dispute` |
| NP-ERR | no promise: promise could not be recorded | `no_promise` | `service_error` |
| NV-FAIL | identity check failed | `not_verified` | `failed` |
| NV-DEC | identity check declined | `not_verified` | `declined` |
| NR-CB | callback booked with a Third Party | `not_reached` | `callback` |
| NR-NCB | no callback time agreed | `not_reached` | `no_callback` |
| NR-WN | wrong number | `not_reached` | `wrong_number` |
| NR-DEC | customer deceased | `not_reached` | `deceased` |
| NR-UNC | could not confirm who answered | `not_reached` | `unclear` |

PTP applies when at least one promise was recorded. Retired codes, never used by the assistant:
PP-AGR (payment plan agreed, retired 2025) and LM (message left, dialler only).

### Transfer queues: values for `transfer_to_agent`

| Code | Team | queue |
|---|---|---|
| Q-RST | Restructuring | `restructuring` |
| Q-GEN | General customer service | `general` |
| Q-SUP | Customer support | `support` |
