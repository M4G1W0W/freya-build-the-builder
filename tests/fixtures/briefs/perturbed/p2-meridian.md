# Meridian Bank: pack for the payment-reminder voice assistant

Meridian Bank is fictional. Every customer, debt, person and payment here is synthetic.

---

**From:** Oluwaseun Adeyemi <o.adeyemi@meridianbank.example>
**To:** Voice Assistant Vendor <delivery@vendor.example>
**Cc:** Hannah Kowalczyk <h.kowalczyk@meridianbank.example>
**Date:** Thu, 8 Oct 2026 17:05 +0000
**Subject:** RE: RE: reminder assistant - final pack (policy, memo, codes)

Hi team,

Hannah's memo landed this afternoon, so I am resending the whole pack in one go. Order of authority,
same as we agreed on the kick-off call: the policy extract (ARR-POL-7 v2.2) is binding, Hannah's memo
amends it and wins on every clause it names, and the CRM code list tells you what to put in the
close_call and transfer_to_agent fields. This e-mail is only context. If I contradict a written
document below, the document is right and I am wrong.

Some context from me (please do not code from it):
- The assistant calls people who are behind on ONE product with us, anything up to 45 days. Over 45
  goes to the external agency, not to us.
- I keep saying "two goes at persuasion for the late ones, one for the early ones". Hannah tells me
  that has not been true since v2.0: it is two for everyone now. Check Schedule B.
- Holidays: Schedule A has them. Ignore the list on the intranet, it is last year's.
- Somebody on our side suggested offering a 10% goodwill reduction to people who pay in full today.
  That has NOT been approved and must not appear anywhere.

Thanks for your patience with us.
Seun

> **From:** Hannah Kowalczyk <h.kowalczyk@meridianbank.example>
> **Date:** Thu, 8 Oct 2026 15:41 +0000
> **Subject:** RE: reminder assistant - final pack
>
> Seun, memo ARR-M-0412 is attached below. Two clauses change, nothing else. The "already paid"
> change is the important one: Payments Operations want every such claim traced while the customer
> is still on the line, because last quarter a third of them were not paid at all.
>
> Also, the dialler team asked whether the assistant should leave voicemails. It should not; the
> dialler handles unanswered calls. Nothing for the vendor to do.
>
> Hannah

> > **From:** Oluwaseun Adeyemi
> > **Date:** Wed, 7 Oct 2026 09:12 +0000
> > **Subject:** reminder assistant - final pack
> >
> > Hannah, can you confirm the late-band deadline before I send this out? I have "8th business day"
> > in my notes but I think Credit Risk shortened it.

---

## EXTRACT: ARR-POL-7 v2.2 "Payment Reminder Calls", Part 3 and Schedules A to C

### Part 3: the automated reminder assistant

**3.1 Definitions.**
(a) "Business Day": Monday to Friday, excluding the Bank Holidays in Schedule A.
(b) "Today": the date in the call variable `now`. All date rules use `now`, never the real clock.
(c) "Customer": the person named in the call variables. "Other Party": anyone else who answers.
(d) "Amount Due" and "Days Late": the `past_due` and `days_late` values returned by `get_account`.
(e) "Floor": `minimum_payment` for a credit card; `instalment_amount` for a personal loan or a car
loan.
(f) "Disposition": a code from Schedule C. Each code fixes the `close_call` outcome and, where
Schedule C gives one, the reason.

**3.2 Call variables.** Each call starts with: `customer_id` (sent with every tool call),
`first_name` and `last_name` (the person to ask for), `title` (`Mr` or `Ms`; the Customer is
addressed as title plus last name), and `now` (date and time, e.g. `2026-10-14T11:00`). Nothing else
is known before a tool is called.

**3.3 Opening.**
3.3.1 The first sentence says the assistant is Meridian Bank's virtual assistant and that the call
is recorded. Until identity is verified the assistant does not say "arrears", "debt", "overdue" or
"payment" and does not name a product, to anyone.
3.3.2 It then asks "Could I speak to {title} {last_name}, please?".
3.3.3 Only "yes", "speaking", "that's me" or the Customer's own name confirms. "Hello", "who is it?"
and "go on" do not. The assistant asks once more. If it is still unclear after the second ask, close
with NC-UNC. A question from the person is answered first (3.3.4, 3.10.5); the ask after it is the
second ask.
3.3.4 Asked whether it is a robot or an AI, the assistant says it is Meridian Bank's virtual
assistant and continues.

**3.4 Other Parties.**
3.4.1 The assistant gives no reason for the call and says nothing beyond the 3.3.1 sentence. It asks
when the Customer can be reached.
3.4.2 A callback is for Today or the next Business Day, from 10:00 to 19:00 inclusive, and later than
`now`. It is booked with `schedule_callback` (date and time). Close with NC-CB.
3.4.3 A day or time outside that window: ask once for another time. If that one is also outside,
book nothing and close with NC-NCB.
3.4.4 "Wrong number": close with NC-WN.
3.4.5 The Customer has died: say "I am sorry for your loss.", ask nothing else, close with NC-DEC.
3.4.6 No Other Party may answer security questions or hear anything about the account, even if they
offer to pay.

**3.5 Identity.**
3.5.1 Two security questions, one at a time: first the date of birth, then the last four digits of
the Customer's current account number. Each answer goes to `verify_identity` as soon as it is given.
The date of birth is sent as `YYYY-MM-DD` however it was said; a date given only as numbers is read
day, month, year.
3.5.2 A wrong answer may be asked again. Two wrong answers in total end the check, on either
question.
3.5.3 If day and month were given the wrong way round, `verify_identity` returns
`hint: "day_month_swapped"`. The assistant asks for the month as a word. That retry is not a wrong
answer.
3.5.4 After two wrong answers: say nothing about the account, direct the Customer to online banking
or a branch, and close with NV-FL.
3.5.5 If the Customer will not answer, the assistant explains once that the questions keep their
account safe. If they still decline, close with NV-DC. Asking what the call is about instead of
answering counts as declining. A second refusal or a second such question ends the call.

**3.6 Stating the arrears.**
3.6.1 After both answers pass, the assistant calls `get_account`.
3.6.2 It says it is calling from Meridian Bank's payments reminder team about a missed payment, names
the product in words ("credit card ending 4821", "personal loan" or "car loan"), and states the Amount
Due and the Days Late.

**3.7 Dates.**
3.7.1 The deadline and the number of persuasion attempts come from Schedule B.
3.7.2 A promise date is Today or later, a Business Day, and not after the deadline.
3.7.3 A weekend day or a Bank Holiday that is not after the deadline: offer the next Business Day. A
date after the deadline: say the latest date that can be recorded is the deadline and offer it;
refusing it is a flat refusal (3.8.3).
3.7.4 A vague period ("next week", "end of the month", "when I get paid"): ask once for the exact
day. If none is given, propose the deadline.
3.7.5 "Next <weekday>" means that weekday in the following calendar week; "this <weekday>" means the
one in the current week.

**3.8 Amounts and persuasion.**
3.8.1 The first ask is "Can you pay the full amount today?". The assistant asks for the full Amount
Due first, never asks "how much can you pay?", and proposes every amount.
3.8.2 If the Customer says the full amount is too much, the assistant offers the Floor, payable on the
next Business Day after Today, once, and says the rest remains overdue. This offer is not a
persuasion attempt. If the Customer refuses it, that is a flat refusal (3.8.3).
3.8.3 A flat refusal or a non-answer uses one persuasion attempt. A no to paying today with no date
and no amount is a flat refusal. A date or an amount the Customer proposes is never a refusal: it is
handled under 3.7 and 3.8.4.
- Attempt 1: the full Amount Due, or the Floor if the Customer already said the full amount is too
  much, on the last Business Day of this week. If Today is that day, the last Business Day of next
  week.
- Attempt 2: the Floor on the deadline.
3.8.4 An amount from the Floor up to the Amount Due, both included, is accepted. Below the Floor: say
it cannot be recorded and offer the Floor once; if not accepted, it is a flat refusal (3.8.3).
3.8.5 When the attempts are used up, stop. Never repeat a refused offer. Close with NP-RF.
3.8.6 Illness, a death in the family or job loss: one short sentence of sympathy, no persuasion
attempt. Offer the customer care team. Accepted: transfer to Q-CARE and close with TR-CARE. Declined:
close with NP-HS. This clause comes before 3.8.3 and 3.10.3. If the Customer still names a date or an
amount themselves, the promise is recorded under 3.7 and 3.8.
3.8.7 No discount, waiver, instalment plan or other term outside this Part may be offered.

**3.9 Confirming and recording.**
3.9.1 Read back the product, the amount and the date, and ask "Shall I record that?". Call
`create_promise` only after a clear yes.
3.9.2 A changed date or amount at this step is checked again under 3.7 and 3.8 and read back again.
3.9.3 One promise per product; a recorded promise cannot be changed or cancelled on this call (the
Customer can change it in online banking).
3.9.4 Say the promise is recorded only after `create_promise` returns `ok: true`. On failure, try once
more. If it fails again, say it could not be recorded and close with NP-SE.
3.9.5 After a recorded promise say: "You will receive a text message confirming this promise."

**3.10 Other things Customers say.**
3.10.1 "I already paid": the assistant says that payments can take one Business Day to appear, takes
no promise, and closes with PD.
3.10.2 "This is not my debt" or "I never had this product": no argument, no promise. Close with
NP-DP. A claim that the product was closed or paid off in the past is a dispute.
3.10.3 A request for a new plan or lower instalments: do not describe a plan. Transfer to Q-RST and
close with TR-RST.
3.10.4 A request for a human: ask once whether the assistant can help first. If the Customer insists,
transfer to Q-GEN and close with TR-HUM. This applies before and after verification.
3.10.5 "Is this a scam?": the Customer can check by calling the number on the back of their Meridian
card; then continue.
3.10.6 A question the tools cannot answer: say the assistant does not have that information. Never
invent figures, dates or reasons.
3.10.7 The Customer says twice they do not want to talk: close with NP-RF. Before identity is
verified, close with NV-DC instead.

**3.11 Closing.**
3.11.1 Every call ends with exactly one `close_call`, carrying the Disposition's outcome and reason. It
is the last tool call. The assistant thanks the Customer and says goodbye before it.
3.11.2 If a transfer follows a recorded promise, close with that transfer's Disposition.
3.11.3 `add_note` is not used on this line.

### Schedule A: Bank Holidays

2026-10-30, 2026-11-11, 2026-12-24, 2026-12-25, 2027-01-01.

### Schedule B: arrears bands

| Days Late | Band | Deadline | Persuasion attempts |
|---|---|---|---|
| 1 to 10 | early | the 10th Business Day after Today | 2 |
| 11 to 45 | late | the 8th Business Day after Today | 2 |

### Schedule C: see the CRM code list below.

---

## MEMORANDUM ARR-M-0412

**From:** Hannah Kowalczyk, Head of Arrears Policy
**To:** Payments Reminder Operations; Voice Assistant Vendor
**Date:** 8 October 2026
**Subject:** Amendments to ARR-POL-7 v2.2, Part 3. In force from the date of this memo.

Only the two clauses below change. Every other clause stays as written.

1. **Schedule B, late band.** The deadline is the 5th Business Day after Today (was the 8th). The
   attempts are unchanged.
2. **Clause 3.10.1** is replaced in full by: "'I already paid': the assistant does not argue and takes
   no promise. It says 'Thank you. I will put you through to our payments team, who can trace that
   payment with you now.', transfers to Q-PAY and closes with TR-PAY. This clause covers only a
   payment of this Amount Due; a claim that the product was closed or paid off in the past is a
   dispute (3.10.2)." Disposition PD is no longer used by the assistant.

Hannah Kowalczyk

---

## CRM CODE LIST (export of 8 October 2026, 16:30)

### Dispositions: values for `close_call`

| Code | Meaning | outcome | reason |
|---|---|---|---|
| PTP | promise to pay recorded | `promise` | (none) |
| PD | customer says it is paid (branch and web only) | `paid` | (none) |
| TR-PAY | transferred to trace a claimed payment | `transferred` | `payment_trace` |
| TR-RST | transferred for a new plan or lower instalments | `transferred` | `restructuring` |
| TR-HUM | transferred on request for a person | `transferred` | `human` |
| TR-CARE | transferred to customer care (hardship) | `transferred` | `support` |
| NP-RF | no promise: refused or did not want to talk | `no_promise` | `refused` |
| NP-HS | no promise: hardship, care declined | `no_promise` | `hardship` |
| NP-DP | no promise: disputed | `no_promise` | `dispute` |
| NP-SE | no promise: promise could not be recorded | `no_promise` | `service_error` |
| NV-FL | identity check failed | `not_verified` | `failed` |
| NV-DC | identity check declined | `not_verified` | `declined` |
| NC-CB | callback booked with an Other Party | `not_reached` | `callback` |
| NC-NCB | no callback time agreed | `not_reached` | `no_callback` |
| NC-WN | wrong number | `not_reached` | `wrong_number` |
| NC-DEC | customer deceased | `not_reached` | `deceased` |
| NC-UNC | could not confirm who answered | `not_reached` | `unclear` |

PTP applies whenever at least one promise was recorded, except 3.11.2. Retired, never used by the
assistant: VM-LEFT (voicemail, dialler only) and PP-OK (payment plan agreed, retired 2025).

### Transfer queues: values for `transfer_to_agent`

| Code | Team | queue |
|---|---|---|
| Q-PAY | Payments Operations | `payments` |
| Q-RST | Restructuring | `restructuring` |
| Q-GEN | General customer service | `general` |
| Q-CARE | Customer care | `support` |
