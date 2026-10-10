# Freya Bank: source material for the collections digital assistant

Freya Bank is fictional. Every customer, debt, person and payment here is synthetic.

---

**From:** Marta Lindqvist <m.lindqvist@freyabank.example>
**To:** Digital Assistant Project <assistant-project@vendor.example>
**Cc:** Tomas Okafor <t.okafor@freyabank.example>; Collections Team Leads <coll-leads@freyabank.example>
**Date:** Fri, 2 Oct 2026 16:42 +0000
**Subject:** RE: RE: assistant for early arrears calls - policy extract (finally!)

Hi all,

Sorry this took so long. Legal wanted to read the extract before it left the building, and then half
of my team went down with the flu. Thanks again for Tuesday's workshop, and apologies for the coffee,
facilities swear the machine is fixed now.

A quick recap in plain words, so you have the picture before you wade into the policy:

The assistant phones our retail customers who have slipped behind on a credit card, a personal loan or
a car loan, anything from a day late up to about six weeks (45 days is the hard cut-off, after that it
belongs to the recoveries team, not to us). Quite a few customers are behind on two or three of these
at once, so please don't build it for one product only.

The flow is basically: introduce yourself as the bank's digital assistant, say the call is recorded,
make sure you actually have the right person, run the two security questions (date of birth first,
then the last four digits of the phone number we hold), and only then say what it's about: how much
is overdue, on which product, how many days late. Then try to get a firm promise, an amount and a date
inside the limits in the policy. Read it back, get a yes, book it, and close the call with the right
code.

Two things my team leads always stress:
- Nothing about the debt to anybody until the person has passed both questions. Not to the husband,
  not to the mum, not even "it's about your credit card". We had a complaint in 2024 about exactly that.
- Never ask "how much can you pay?". We propose the numbers. Ask that and everyone says a tenner.

On the security questions, I think the rule is three wrong answers per question? Tomas, correct me.
Either way section 4.4 of the policy is the binding wording, follow that and not my memory.

Tone: calm, polite, short sentences, Mr or Ms plus the surname. No pressure, no threats, no "final
notice" talk, and nothing we haven't put in writing: no discounts, no "we can probably waive the fee",
no payment plans. Anyone who wants a plan goes to the restructuring people, and anyone who insists on a
human goes to the general queue. Callbacks when someone else picks up: 10 till 7, see 4.3.

FYI because someone asked on Tuesday: the dialler only places calls between 09:00 and 20:00, Monday to
Saturday. That is set on the dialler side by Tomas's team; the assistant doesn't need to do anything
with it.

Also, there was talk at the September steering group about giving the early band more time (15
business days instead of 12). Nothing is decided. Don't build it unless it turns up in writing.

Pasted below is the extract of COL-POL-004 v4.1 (section 4 and the schedule you need, the rest is
about letters and field agents). The code list will follow separately: the CRM team will re-export it
once Compliance have finished the review they are doing. If anything changes it will come to you as a
memo, and a memo overrides the policy for the clauses it names.

Have a good weekend,
Marta

--
Marta Lindqvist
Head of Retail Collections | Freya Bank
"Fair, firm, on time."

CONFIDENTIALITY NOTICE: This e-mail and any attachment are confidential and intended only for the
named recipients. If you received it in error, please tell the sender and delete it. Freya Bank does
not accept liability for changes made to this message after it was sent.

> -----Original Message-----
> From: Digital Assistant Project <assistant-project@vendor.example>
> Sent: Tuesday, 29 September 2026 09:12
> To: Marta Lindqvist
> Subject: RE: assistant for early arrears calls
>
> Hi Marta, could you send us the written policy and the list of codes your CRM expects? We will build
> only from what is written down. Thanks!

---

## POLICY EXTRACT: COL-POL-004 "Collections Contact Policy"

| Document | COL-POL-004 |
|---|---|
| Version | 4.1 |
| Approved | Credit Risk Committee, 18/08/2026 |
| Effective | 01/09/2026 |
| Owner | Head of Retail Collections |
| Classification | INTERNAL |

Version history: v4.0 (01/03/2026) introduced Section 4 for single-product calls; v4.1 (01/09/2026)
extends Section 4 to customers with up to three Products in arrears.

*[Sections 1 to 3 (written notices, field visits, hand-over to recoveries) and clauses 4.13 to 4.15
(quality monitoring, data retention, complaints) are not reproduced in this extract.]*

### Section 4: Outbound calls placed by the digital assistant

**4.1 Scope and definitions**

4.1.1 This Section governs outbound calls placed by the Bank's digital assistant (the "Assistant") to
retail customers (each a "Customer") who are between one (1) and forty-five (45) days late
(`days_late`), both inclusive, on one or more Products.

4.1.2 "Product" means a credit card, a personal loan or a car loan. A Customer may be late on up to
three (3) Products at the time of the call.

4.1.3 "Business Day" means Monday to Friday, other than a Bank Holiday listed in Schedule 2.

4.1.4 "Today" means the date contained in the call variable `now`. Every date and time rule in this
Section is applied to `now` and never to the system clock.

4.1.5 "Floor Amount" means, for each Product, the amount identified in Table 3 (clause 4.7.2).

4.1.6 At the start of each call the Assistant receives the data below and no other information until
the Bank's systems are queried.

| Variable | Example | Use |
|---|---|---|
| `customer_id` | `c_9b1e...` | Passed on every system call. |
| `first_name`, `last_name` | `Helen`, `Marsh` | The person to ask for. |
| `title` | `Mr` or `Ms` | Form of address: title plus last name. |
| `now` | `2026-10-14T11:00` | The current date and time. |

**4.2 Opening of the call**

4.2.1 The first sentence of the Assistant shall state that it is a digital assistant calling from
Freya Bank and that the call is recorded.

4.2.2 Before identity has been verified under 4.4, the Assistant shall not use the words
"collections", "debt" or "payment" and shall not name any Product. This restriction applies to every
person on the line, relatives of the Customer included.

4.2.3 The Assistant shall then ask: "Am I speaking with {title} {last_name}?"

4.2.4 Only "yes", "that's me", "speaking" or the Customer's own name constitutes confirmation.
Responses such as "hello", "go ahead" or "who is this" do not. Where confirmation is not obtained the
Assistant asks once more. Where it remains unclear after the second ask, the call is closed
`not_reached` / `unclear`. Where the person asks a question, the Assistant answers it first (clauses
4.2.5 and 4.10.5); the ask that follows is the second ask.

4.2.5 Where asked whether it is a robot or an AI, the Assistant states that it is Freya Bank's
digital assistant and continues.

**4.3 Calls answered by a third party**

4.3.1 The Assistant shall not state the reason for the call and shall say nothing beyond the opening
sentence under 4.2.1. It asks when the Customer can be reached.

4.3.2 A callback may be booked for Today or the next Business Day, between 10:00 and 19:00 (both
times included), and later than `now`. The Assistant books it by calling `schedule_callback` with the
date and the time, and closes the call `not_reached` / `callback`.

4.3.3 Where the person offers a day or a time outside the window of 4.3.2, the Assistant asks once
for another time. Where that is also outside the window, no callback is booked and the call is closed
`not_reached` / `no_callback`.

4.3.4 Where the person states that the number does not belong to the Customer, the call is closed
`not_reached` / `wrong_number`.

4.3.5 Where the person states that the Customer has died, the Assistant says
"I am sorry for your loss.", asks nothing further, and closes the call `not_reached` / `deceased`.

4.3.6 A relative shall not answer the security questions and shall not be told anything about the
account, including where the relative offers to pay.

**4.4 Identity verification**

4.4.1 Two security questions are asked, one at a time, in the order of Table 2. Each answer is
checked by calling `verify_identity`.

*Table 2: Security questions*

| Order | Question put to the Customer | `field` | Value sent to the system |
|---|---|---|---|
| 1 | Date of birth | `date_of_birth` | `YYYY-MM-DD`, whatever way the Customer said it. The service rejects anything it cannot read as a date. A date given only as numbers is read as day, then month, then year. |
| 2 | Last four digits of the phone number on file | `phone_last4` | Four digits. |

4.4.2 A question answered wrongly may be asked again. Three (3) wrong answers in total end the check,
whichever question they were given on.

4.4.3 Where `verify_identity` returns `hint: "day_month_swapped"`, the Assistant asks the Customer to
say the month as a word. That retry is not counted as a wrong answer.

4.4.4 After three wrong answers the Assistant shall not state the debt, shall tell the Customer to use
the mobile app or a branch, and closes the call `not_verified` / `failed`.

4.4.5 Where the Customer does not wish to answer, the Assistant explains once that the questions
protect their account. Where the Customer still declines, the call is closed `not_verified` /
`declined`. Asking what the call is about instead of answering counts as declining. A second refusal,
or a second such question, closes the call.

**4.5 Statement of arrears**

4.5.1 Once both questions are passed, the Assistant calls `get_account`. It returns one to three
Products, each with its own `past_due`, `days_late` and Floor Amount.

4.5.2 The Assistant states that it is calling from the collections team about a late payment, names
the Product in words ("credit card ending 4821", "personal loan" or "car loan"), and states the
past-due amount and the number of days late.

4.5.3 Where more than one Product is late, every late Product is stated, one sentence each, before
anything is asked of the Customer.

**4.6 Dates and deadlines**

4.6.1 The arrears band and the deadline are set per Product, from that Product's `days_late`, in
accordance with Table 1. Two Products of the same Customer may have different deadlines.

*Table 1: Arrears bands*

| Band | `days_late` | Deadline (latest promise date) | Maximum persuasion attempts |
|---|---|---|---|
| Early | 1 to 7 | the twelfth (12th) Business Day after Today | 1 |
| Late | 8 to 45 | the seventh (7th) Business Day after Today | 2 |

4.6.2 A promise date shall be Today or later, a Business Day, and not after the deadline.

4.6.3 Where the Customer names a Saturday, a Sunday or a Bank Holiday that is not after the deadline,
the Assistant offers the next Business Day. Where the named day is after the deadline, 4.6.6 applies.

4.6.4 Where the Customer gives a vague period ("next week", "end of the month", "when my salary
comes"), the Assistant asks once for the exact day. Where none is given, the Assistant proposes the
deadline.

4.6.5 "Next <weekday>" means that weekday in the following calendar week. "This <weekday>" means that
weekday in the current week. Accordingly, "next Friday" said on a Friday is the Friday of the
following week.

4.6.6 Where the Customer asks for a date after the deadline, the Assistant states that the latest date
it can record is the deadline and offers it. A refusal of the deadline is a flat refusal (4.8.3).

4.6.7 Where the Customer names one date for all Products and that date is after one Product's
deadline, that Product is recorded on its own deadline and the Assistant says so in the read-back. The
other Products keep the date the Customer named.

**4.7 Amounts**

4.7.1 The Assistant first asks for the full past-due amount. The Assistant shall never ask "how much
can you pay?"; it proposes every amount itself.

4.7.2 The Floor Amount is determined by the Product type in accordance with Table 3.

*Table 3: Floor Amount*

| Product | `type` | Field holding the Floor Amount |
|---|---|---|
| Credit card | `credit_card` | `minimum_payment` |
| Personal loan | `personal_loan` | `instalment_amount` |
| Car loan | `car_loan` | `instalment_amount` |

4.7.3 Where the Customer states that the full amount is too much, the Assistant offers the Floor
Amount, once, and states that the rest remains overdue. A refusal of the Floor Amount is a flat
refusal (4.8.3). Attempt 2 may name the Floor Amount again, on the deadline.

4.7.4 An amount proposed by the Customer from the Floor Amount up to the full past-due amount, both
included, is accepted. Below the Floor Amount, the Assistant states that it cannot be recorded and
offers the Floor Amount once. Where the Customer does not accept the Floor Amount, this is a flat
refusal (4.8.3).

**4.8 Obtaining the promise**

4.8.1 The first ask is: "Can you make this payment today?". Where more than one Product is late, the
Assistant first asks whether the Customer can pay all of them today. If not, it takes the Products one
by one in the order returned by `get_account`, does not ask about today again for each Product, and
starts each Product at attempt 1 of 4.8.3.

4.8.2 A date or an amount proposed by the Customer is never a refusal. It is handled under 4.6 and
4.7.

4.8.3 A flat refusal or a non-answer uses one persuasion attempt. A "no" to paying today, with no date
and no amount, is a flat refusal. Attempt 1 is for the full past-due amount, or for the Floor Amount
where the Customer has already said that the full amount is too much.

> (a) Attempt 1: propose the last Business Day of the current week. Where Today is that day, propose
> the last Business Day of the following week.
>
> (b) Attempt 2, Late band only: propose the Floor Amount on the deadline.

4.8.4 Persuasion attempts are counted per Product.

4.8.5 When the attempts are used up, the Assistant stops. It shall not repeat an offer the Customer
has already refused. The call is closed `no_promise` / `refused`, subject to 4.11 and 4.12 where
several Products are concerned.

4.8.6 Where the Customer mentions illness, a death in the family or the loss of their job, the
Assistant says one short sentence of sympathy, makes no persuasion attempt, and offers to connect the
Customer with the customer support team. Where the Customer accepts, the Assistant calls
`transfer_to_agent` with queue `support` and closes the call `transferred` / `support`. Where the
Customer declines, the call is closed `no_promise` / `hardship`. This clause takes precedence over
4.8.3 and 4.10.3. Where the Customer nevertheless names a date or an amount, the promise is recorded
under 4.6 and 4.7.

4.8.7 The Assistant shall not offer a discount, a waiver, an instalment plan or any other term that
is not set out in this Section.

**4.9 Confirmation and recording**

4.9.1 The Assistant reads back the Product, the amount and the date and asks "Do you confirm?".
`create_promise` is called only after a clear yes. Where there are several promises, all of them are
read back together with one request for confirmation, and `create_promise` is then called once per
Product.

4.9.2 Where the Customer changes the date or the amount at this point, the new value is checked under
4.6 and 4.7 and read back again.

4.9.3 One promise per Product. A recorded promise cannot be changed or cancelled during the same call.
A Customer who asks is told that they can change it in the mobile app.

4.9.4 The Assistant states that a promise is recorded only after `create_promise` returns `ok: true`.
On failure it tries once more. Where it fails again, the Assistant says that it could not record the
promise. Promises already recorded for other Products are kept, a note with reason `service_error` is
added for the failed Product (4.11.1), and the outcome follows 4.12 (with one Product: `no_promise` /
`service_error`).

4.9.5 After a recorded promise, the Assistant says this sentence:
"You will receive a text message confirming this promise."

**4.10 Other situations**

4.10.1 "I already paid": the Assistant says that payments can take one Business Day to appear and
takes no promise for that Product. Where the Customer's only late Product is concerned, the call is
closed `paid`.

4.10.2 "This debt is not mine" or "I never had this product": the Assistant does not argue and takes
no promise for that Product. With one Product, the call is closed `no_promise` / `dispute`. A claim
that the Product was closed or paid off in the past is a dispute; 4.10.1 covers only a payment of the
current past-due amount.

4.10.3 A request for a new payment plan or for lower instalments: the Assistant does not describe any
plan, calls `transfer_to_agent` with queue `restructuring`, and closes the call `transferred` /
`restructuring`. Promises recorded before the request remain. Promises agreed but not yet recorded are
not recorded.

4.10.4 A request for a human: the Assistant asks once whether it can help first. Where the Customer
insists, it calls `transfer_to_agent` with queue `general` and closes the call `transferred` /
`human`.

4.10.5 "Is this a scam?": the Assistant says that the Customer can verify the call by phoning Freya
Bank's customer service number, and continues.

4.10.6 A question the Assistant cannot answer from the systems: it says that it does not have that
information. It shall not invent figures, dates or reasons.

4.10.7 Where the Customer says twice that they do not want to talk, the call is closed `no_promise` /
`refused`. Before identity is verified, the same Customer is closed `not_verified` / `declined`.
Clause 4.10.4 applies both before and after verification.

**4.11 Notes**

4.11.1 For each Product without a promise the Assistant calls `add_note` with that `product_id` and
one of the reasons `refused`, `hardship`, `dispute`, `paid` or `service_error`. This applies also
where no Product receives a promise.

4.11.2 A dispute or an "already paid" claim on one Product does not end the call. It is noted and the
Assistant continues with the other Products.

4.11.3 On any transfer (restructuring, support or human) no notes are added at all, before or after
the transfer.

**4.12 Closing**

4.12.1 Every call ends with exactly one `close_call`, carrying an outcome and, where Table 4 lists
one, a reason. It is the last system call.

*Table 4: Call outcomes*

| Outcome | Reason | Clause |
|---|---|---|
| `promise` | none | at least one promise was recorded |
| `paid` | none | 4.10.1 |
| `transferred` | `restructuring`, `human`, `support` | 4.10.3, 4.10.4, 4.8.6 |
| `no_promise` | `refused`, `hardship`, `dispute`, `service_error` | 4.8.5 and 4.10.7, 4.8.6, 4.10.2, 4.9.4 |
| `not_verified` | `failed`, `declined` | 4.4.4, 4.4.5 |
| `not_reached` | `callback`, `no_callback`, `wrong_number`, `deceased`, `unclear` | 4.3.2, 4.3.3, 4.3.4, 4.3.5, 4.2.4 |

4.12.2 Where a transfer follows a recorded promise, the call is closed `transferred` with that
transfer's reason.

4.12.3 Where no promise was recorded: if every Product is noted `paid`, the outcome is `paid`;
otherwise the outcome is `no_promise` with the reason of the first Product, in `get_account` order,
whose note is not `paid`. With several Products, `promise` prevails whenever at least one promise was
recorded, save as provided in 4.10.3.

4.12.4 Before `close_call` the Assistant thanks the Customer and says goodbye.

**Schedule 2: Bank Holidays** (branches closed; not Business Days)

| Date | Day |
|---|---|
| 26/10/2026 | Monday |
| 11/11/2026 | Wednesday |
| 26/11/2026 | Thursday |
| 25/12/2026 | Friday |
| 01/01/2027 | Friday |

*End of extract.*

---

## MEMORANDUM

**FREYA BANK, Compliance and Collections Strategy**

| | |
|---|---|
| Ref | COL-MEMO-2026-17 |
| Date | 07/10/2026 |
| To | Head of Retail Collections; Collections team leads; Digital assistant project team |
| From | J. Ferreira, Compliance Officer, Retail Credit |
| Subject | Amendments to COL-POL-004 v4.1, Section 4 (digital assistant), effective immediately |

**1. Purpose.** This memorandum amends COL-POL-004 version 4.1 with effect from the date above and
supersedes the clauses it names. Where this memorandum and the policy differ, this memorandum
prevails. All other clauses remain in force without change.

**2. Amendments.**

2.1 *Persuasion attempts, Late band (Table 1; clauses 4.7.3 and 4.8.3).* The maximum number of
persuasion attempts for the Late band (8 to 45 days late) is raised from two (2) to three (3). Insert
in 4.8.3: "(c) Attempt 3, Late band only: propose the Floor Amount again and ask the Customer to name
any Business Day, up to and including the deadline, on which they can pay it." In 4.7.3, read
"Attempt 2 and attempt 3 may name the Floor Amount again". The Early band remains at one (1) attempt.

2.2 *Bank Holidays (Schedule 2).* Delete 11/11/2026: it is an ordinary Business Day and branches will
open as normal. Insert Friday 30 October 2026 (branch network closed for the core banking migration).
All other dates stand.

2.3 *Callback window (clause 4.3.2).* Replace "between 10:00 and 19:00 (both times included)" with
"between 10:00 and 18:00 (both times included)". A callback at 18:00 may still be booked. The earliest
time and the days (Today or the next Business Day, later than `now`) are unchanged.

2.4 *Transfer queue on a request for a human (clause 4.10.4).* Following the telephony upgrade, the
queue `general` has been renamed `service_desk`. Replace "queue `general`" with "queue
`service_desk`". The queue `general` no longer exists. The outcome and reason remain `transferred` /
`human`. The queues `restructuring` and `support` are unchanged.

2.5 *Confirmation sentence (clause 4.9.5).* Replace the sentence with:
"We will send you a text message with the details of this promise."
It is said at the same point as before, after a recorded promise.

2.6 *Outcome code `not_reached` (clauses 4.2.4, 4.3.2 to 4.3.5, Table 4).* The CRM outcome code
`not_reached` is retired and replaced by `no_contact`. Every reference to `not_reached` in Section 4 is
to be read as `no_contact`. The reasons that go with it (`callback`, `no_callback`, `wrong_number`,
`deceased`, `unclear`) are unchanged.

**3. For the avoidance of doubt.** The proposal discussed at the September steering group to move the
Early band deadline to the fifteenth Business Day has not been approved. The deadlines in Table 1 are
unchanged: Early, the 12th Business Day after Today; Late, the 7th Business Day after Today.

J. Ferreira
Compliance Officer, Retail Credit
cc: M. Lindqvist; T. Okafor

---

## CODE LIST: values for close_call and add_note

Source: CRM table `COLL_OUTCOME_CODES`, export of 08/10/2026 (includes COL-MEMO-2026-17).
Send the value in column `code` exactly as written. `crm_id` is internal and is never sent.

```
crm_id;kind;code;used_in;description;status
OC-01;outcome;promise;close_call.outcome;At least one payment promise recorded on the call;active
OC-02;outcome;paid;close_call.outcome;Customer says the past-due amount is already paid;active
OC-03;outcome;transferred;close_call.outcome;Call handed over to a human queue;active
OC-04;outcome;no_promise;close_call.outcome;Customer verified but no promise recorded;active
OC-05;outcome;not_verified;close_call.outcome;Identity check not passed;active
OC-06;outcome;not_reached;close_call.outcome;Customer not reached;DEPRECATED - do not use (replaced by no_contact)
OC-07;outcome;no_contact;close_call.outcome;Customer not reached or not confirmed on the line;active
RC-01;reason;restructuring;close_call.reason with transferred;Customer asked for a new plan or lower instalments;active
RC-02;reason;human;close_call.reason with transferred;Customer insisted on speaking to a person;active
RC-03;reason;support;close_call.reason with transferred;Hardship and customer accepted the support team;active
RC-04;reason;refused;close_call.reason with no_promise / add_note.reason;No promise after the persuasion attempts or customer does not want to talk;active
RC-05;reason;hardship;close_call.reason with no_promise / add_note.reason;Hardship and customer declined the support team;active
RC-06;reason;dispute;close_call.reason with no_promise / add_note.reason;Customer disputes the debt or the product;active
RC-07;reason;service_error;close_call.reason with no_promise / add_note.reason;Promise could not be recorded after a retry;active
RC-08;reason;paid;add_note.reason;Customer says this product's past-due amount is already paid;active
RC-09;reason;failed;close_call.reason with not_verified;Three wrong security answers;active
RC-10;reason;declined;close_call.reason with not_verified;Customer declined the security questions;active
RC-11;reason;callback;close_call.reason with no_contact;Callback booked with the person who answered;active
RC-12;reason;no_callback;close_call.reason with no_contact;No callback time inside the window;active
RC-13;reason;wrong_number;close_call.reason with no_contact;Number does not belong to the customer;active
RC-14;reason;deceased;close_call.reason with no_contact;Customer reported deceased;active
RC-15;reason;unclear;close_call.reason with no_contact;Person on the line not confirmed after two asks;active
RC-16;reason;third_party;close_call.reason with no_contact;Someone other than the customer answered;DEPRECATED - do not use (use callback or no_callback)
```
