# E4-A-styledA analysis (copy of the gitignored `runs/dev/r4/analysis-e4a.md`; COMPLETED, removed from the queue 14:09 UTC) (cand-eng.4 cfa4d9d on exp-eng4-a, styled-a.json, 11 Oct 13:29-13:50 UTC)

Harness: run_one.sh + suite_once.py (scratch, session 6099f72d): POST maxRetries 0, no reruns, every simulation in
`E4-A-styledA.attempts.jsonl` (reps 1-2) and `E4-A-styledA-r3.attempts.jsonl` (rep 3); call records in
`E4-A-styledA.calls/`. Read-only analysis workflows: wf_cae6672e-5d3 (rep-1 classification + skeptics, reps 1-2
audit), wf_5a767735-790 (rep-3 audit); smoke: wf_d1cd9ea9-206.

## 1. Score (raw, nothing excluded)

| Case | r1 | r2 | r3 | 3/3 |
|---|---|---|---|---|
| PUB-01 | F | P | P | no |
| PUB-02 | P | P | P | yes |
| PUB-03 | F | P | P | no |
| PUB-04 | F | P | P | no |
| PUB-05 | P | P | P | yes |
| PUB-06 | F | P | P | no |
| PUB-07 | P | P | P | yes |
| PUB-08 | F | P | P | no |
| PUB-09 | P | P | P | yes |
| PUB-10 | F | P | P | no |

Reps 4/10 (sim 56096a1e), 10/10 (5407adea), 10/10 (51c4a5e0). **Strict 3/3: 4/10.** Control M3 G1 (exp-g1-a, same
cases, 08:30 UTC): 10/10, all 30 runs first attempt (attempts 0 of 4), medians 4/4/8 s.

## 2. Failure classification (rep 1 only; reps 2-3 had none)

- **PUB-01, 03, 04, 08, 10: platform, model requests hung/lost** (skeptic: not refuted). After the customer's first
  answer the platform logged no event for 60.31-60.33 s (simulator silence limit), then customer-ended-call. The
  pending step was the opening node's who_answered extraction (the first model request of each call). Identical
  customer text extracted in 0.3-11.8 s in reps 2-3 on the same workflow; other rep-1 calls progressed meanwhile.
  Agent contribution: none identifiable. The opening node is byte-identical to G1's (equal exposure).
- **PUB-06: mixed** (skeptic: not refuted, corrections applied). Trigger: platform `extraction_error` (who_answered,
  empty error, 13.96 s). Our design then turned it into a ledger/policy failure: who_answered is judged "from the
  latest message", so later turns could not recover; the opening node has no tools; the model called a
  verify_identity it did not have (4x, fabricated customer_id; nothing reached the bank), said "technical issue"
  twice, used rule 14's app/branch line with zero wrong answers, and closed `not_verified/declined` although the
  customer gave her DOB three times and never declined (untrue reason in the bank record). Same opening in G1.

## 3. Latent findings in passing calls (judge only scores each case's listed checks)

1. **Rule 47 skipped on transfers** ("Thank the customer and say goodbye before close_call"): PUB-09 3/3 eng.4 and
   3/3 G1 (M3) end "...restructuring team." with no thanks/goodbye. Shared, systematic; a hidden case checking the
   closing would fail.
2. **Read-back without the product** (rule 34) when the customer names the date: PUB-10 r3 and G1 3/3 ("Friday 16
   October 2026 is a business day. Do you confirm you will pay 365.00 ..."). Shared; eng.4 r2 did a full read-back.
3. **False weekday statement**: PUB-07 r1 838082e6 "Monday 27 October 2026 is a business day" (27 Oct is a
   Tuesday) after the customer said only "Monday." inside "the week after next". Rescued by the customer adding "the
   26th". G1's M3 PUB-07 calls had no such line (customers gave the day number); eng.4-specific or not: undetermined.
4. Hardship wording varies (r1 a second "sorry" vs the check "one sentence of sympathy"); asks_back vs rule 15's
   "second such question closes the call"; questions inside an answer often unanswered (varies by run).
5. **Latency margin**: by messageId delivery stamps [I] the kit's slowest-turn metric undercounts (rep 2 worst 58.2 s
   vs reported 35 s); three rep-2 passes came within 2-5 s of the 60 s hang-up limit. The longest waits are tool
   turns that need a second model pass to speak.

Clean everywhere: opening sentence, nothing disclosed before all_verified, get_account only after verification,
"recorded" never before ok:true, exactly one close_call last with the right outcome/reason (except PUB-06 r1).
