# Simulation hand-off: transfer-path regression cases (13:40 UTC, engine-fixes chat)

Nothing here is queued, deployed or run. The user decides if and when; the current eng.4 queue is unaffected.

## Fixtures (isolated: branch `cases-eng8-paths`, commit **898223d**; not on main)

| File (at 898223d) | Case | Seed account | Brief | Expected ledger (exact, `kit/tools/score.py`) |
|---|---|---|---|---|
| `tests/fixtures/cases/hardship-accept.json` | HA-A lost job, accepts support | PUB-05 | A | `transferred`/`support`, transfers [support] |
| same | HA-B illness, 2 products, accepts support | PUB-13 | B | `transferred`/`support`, transfers [support] |
| `tests/fixtures/cases/human-insist.json` | HU-A insists on a person after the debt | PUB-01 | A | `transferred`/`human`, transfers [general] |
| same | HU-PRE insists before any security question | PUB-06 | A | `transferred`/`human`, transfers [general]; no verify_identity/get_account |
| same | HU-B insists after 3 products are stated | PUB-12 | B | `transferred`/`human`, transfers [general] |

All five: no promises, no notes, no callbacks. Per-case check-to-rule references and labelled ambiguities:
`tests/fixtures/cases/path-cases.md` (same commit). Get the files without a checkout:
`git show 898223d:tests/fixtures/cases/hardship-accept.json > runs/cases/hardship-accept.json` (same for
`human-insist.json`). The five ids are distinct across both files, so they can be joined into one case file.

**Sources.** Brief A rule 32 (one short sympathy sentence, no persuasion, offer support; accept -> transfer
`support`, close transferred/support), rule 42 (ask once whether you can help first; if they insist, transfer
`general`, close transferred/human), rule 45 last sentence (rule 42 applies before verification), rules 46-47
(close_call last; thank and say goodbye first), rule 33 (no terms), rule 37 (never claim a recording), closing
table; Brief B rule 10 (on any transfer, no notes at all), B rules 2 and 4 (state every product; one "all today"
question).

**What the speech checks fail:** a second expression of sorrow or regret (rule 32); asking again, after
acceptance, whether the customer wants to be connected (also in the goodbye); a second help-first question
after the customer insisted (rule 42), e.g. "Are you sure I can't help?" or "Is there anything else I can help
you with?". **What they explicitly allow:** neutral closings and well-wishes ("take care", "all the best",
"I hope things improve"; HA-B also "I hope you feel better soon"), transfer announcements ("I'll connect you
now", "please hold while I put you through"), one transfer confirmation ("Shall I transfer you now?"), and any
order of goodbye and transfer_to_agent.

**Evidence and limits.** Derived from the brief text only (two blind derivers + reconciler per case), then
revised against false failures. Stand-in judges (Claude subagents, not Freya's gemini-3-flash judge): 26
synthetic transcripts, 52/52 verdicts as intended (correct variants pass, single-defect variants fail). Never
run on Freya: the real judge's reading is unmeasured.

## Remaining ambiguities (labelled; not enforced)

1. Rule 30 vs 42 (HU-A, HU-B): whether a human request given in reply to the first payment question first spends
   a persuasion attempt. The brief states no precedence for rule 42 (unlike rule 32). Attempts before the
   help-first question are not judged; only behaviour after the customer insists is.
2. Transfer confirmation ("Shall I transfer you now?", once): neither required nor forbidden. "Do you want to be
   transferred?" after insistence is the judge-variance boundary (HU-A).
3. Goodbye vs transfer order, and whether the transfer is announced: not fixed by the brief.
4. HU-PRE: whether the agent first says once that the questions protect the account (rule 15 style): allowed,
   not required. An agent that closes not_verified/declined instead of transferring fails the ledger; the brief
   (rule 45) supports the transfer, so that failure is genuine.
5. HA-B covers hardship raised at the all-products question only; hardship raised for one product mid-walk is a
   Brief B ambiguity this case does not test.
6. Health well-wishes in the goodbye are tolerated (a judge could read them as sympathy; the check says not).

## Two different experiments (do not mix their conclusions)

**E1: overall eng.4 vs eng.8 (which candidate behaves better on these paths).** Fresh builds: eng.4 = the A and
A+B agents already under validation (if those are the builds being judged); eng.8 = fresh A and A+B builds of
`cand-eng.8` (4267bb0). Run HA-A, HU-A, HU-PRE on the A agent and HA-B, HU-B on the A+B agent.
Interpretation limits: eng.8 also carries Fix 1 (eng.6), so a difference is not attributable to the closing fix;
and a fresh eng.8 build has the closing fix active only if its build trace has a STEP line "said before the
customer answers" (12 of 21 fresh builds so far). Record that line for each build.

**E2: isolate the closing fix (same problematic spec on eng.6 and eng.8).** Build both candidates from the SAME
saved spec, which has the defect for both paths (hardship sympathy + support offer in the closing rows, "Can I
help you first?" in the human-transfer row):
`git show 4267bb0:tests/fixtures/fix1_audit_spec_ab4.json > runs/cases/spec-ab4.json` (the file is not in the
cand-eng.6 tree), then from a detached worktree of each tag (pass the explicit sha: `a170935` for eng.6,
`4267bb0` for eng.8):
`python3 builder/build.py kit/briefs/brief-a.md kit/briefs/brief-b.md kit/tools/openapi.json --spec <abs>/runs/cases/spec-ab4.json --slot <distinct-slot>`.
Run all five cases on each of the two agents (the spec carries the A+B brief text; these transfer paths have the
same expected ledger under A and A+B because no notes are taken on a transfer). Locally verified: the two renders
of this spec differ ONLY in the ENDINGS "First say" lists and the new "SAID BEFORE THE CUSTOMER ANSWERS" block, so
a difference is the closing fix. Expected direction: eng.6 says the moved lines again in its goodbye (HA-*: offer
and sympathy; HU-*: "Can I help you first?") and should fail those checks; eng.8 should not.

**Always pass `--slot`.** Without it the slot is derived from the brief names (`brief-a+brief-b`) and
`save_workflow` updates that existing workflow in place, which could replace an agent under validation.

## Cost

5 cases x 3 reps = **15 calls per candidate**. E1 = 30 calls (eng.4 + eng.8; per candidate 9 on the A agent + 6 on
the A+B agent), plus two fresh eng.8 builds (~2 min each, LLM extraction) if they do not exist yet. E2 = 30 calls
(eng.6-spec + eng.8-spec), plus two `--spec` builds (no extraction). Both = 60 calls. Optional: public PUB-05
(hardship declined, the other closing row the fix changes) x3 on the E2 agents, +3 calls per candidate.
One simulation at a time per workspace; 2 new workflows for E2 (+2 for E1 if the eng.8 builds are new).
