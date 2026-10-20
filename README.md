# Shift Pay Checker

A GenLayer Intelligent Contract that answers: **is a steward owed money for shift time the agency didn't pay?**

An agency sets out the agreed terms (rate, scheduled hours, break rules) and the steward accepts them by hash. After the event, the steward claims each period of unpaid time. The agency acknowledges the exact claim and responds to each item. GenLayer validators each fetch the event's sign-in log, independently rule UPHOLD or REJECT on every claim, quote the log or the terms word for word, and must agree. Code then works out the money owed and adds it to the agency's public pay record. Either side may appeal once.

Example: the log shows the steward signed out at 00:10 after a 23:00 scheduled finish because the event overran, so 70 minutes is **UPHOLD**. The log records the break as unpaid, so a claim for the break is **REJECT**.

## Why I built it

I work in security and events in the UK. Events overrun, stewards stay on for egress, people get sent home early, and the extra time often goes unpaid or gets argued about weeks later. The sign-in sheet usually has the answer. This contract makes the agreed terms and the sign-in record the deciding evidence, and gives every agency a public record of how often it underpays.

## What is implemented

- **Two distinct parties.** Agency and steward must be different addresses.
- **Consent to the exact terms.** The agency's terms get a fingerprint (`terms_hash`). The steward must accept that exact hash before claiming.
- **Consent to the exact claim.** When the steward closes the claim, it gets a `claim_hash`. The agency must acknowledge that exact hash before responding.
- **Evidence fetched by validators.** Each validator fetches the sign-in log from its link itself.
- **Verified quotes.** Each decision must quote the sign-in log or agreed terms word for word, and the contract checks every quote. Made-up quotes are rejected.
- **Independent agreement.** Using `gl.vm.run_nondet_unsafe`, each validator rules every claim itself and must reach exactly the same UPHOLD/REJECT labels as the leader, then audits the leader's quotes and reasons.
- **Code decides the money.** The AI cannot set minutes, pay, statuses or records. Pay owed = upheld minutes × agreed hourly rate, worked out by code.
- **No state changes until the ruling passes every check.** A malformed AI reply is asked again (up to 3 attempts).
- **One appeal** by either party, then the ruling is final.
- **Agency pay record:** engagements, claims, claims upheld, minutes claimed and upheld, pence owed.
- **Five isolated fictional demos**, including a prompt-injection case. Demos never create engagements or records.

## Lifecycle

| Step | Who | Method | Status after |
|---|---|---|---|
| Set terms | Agency | `create_engagement(steward_address, rate_pence_per_hour, event_name, agreed_terms, sign_in_log_url)` | PROPOSED |
| Accept exact terms | Steward | `accept_terms(engagement_id, expected_terms_hash)` | ACTIVE |
| Claim unpaid time (1-6) | Steward | `add_claim(engagement_id, shift_date, minutes, steward_reason)` | ACTIVE |
| Close the claim | Steward | `close_claims(engagement_id)` | AWAITING_AGENCY |
| Acknowledge exact claim | Agency | `acknowledge_claims(engagement_id, expected_claim_hash)` | AWAITING_RESPONSES |
| Respond to each claim | Agency | `respond(engagement_id, claim_number, agency_response)` | AWAITING_RESPONSES |
| Finish | Agency | `finish_response(engagement_id)` | READY |
| Rule | Anyone | `rule(engagement_id)` | RULED |
| Accept | Either party | `finalise(engagement_id)` | FINAL |
| Or appeal once, then rule | Either party, then anyone | `appeal(engagement_id, reason)` → `rule` | APPEALED → FINAL |

Read methods: `get_engagement`, `get_engagement_summary` (shows both hashes), `get_counts`, `get_agency_record`, `get_policy`, `get_demo`, `get_demo_result`, `get_demo_summary`. Demo write: `run_demo(case_id)`.

## Policy (summary)

1. Unsupported or unclear claims are rejected.
2. Time between signing in and signing out in the log counts as worked.
3. A break the log records as unpaid isn't payable, unless the terms say breaks are paid.
4. Time worked past the scheduled finish is payable.
5. If the terms promise a minimum shift and the steward was sent home early, the shortfall is payable.
6. If the log can't be read, claims are rejected unless the agency admits them.

The full text is returned by `get_policy`.

## Quick start in Studio

1. Import `contract.py` into GenLayer Studio and deploy with no arguments.
2. Call `run_demo` with `case_id = 1` and wait for it to be accepted.
3. Call `get_demo_summary` with `result_id = 0`. Expected: decision `UPHOLD`, `matches_expected: true`, `records_created: false`.

See [DEMO_GUIDE.md](DEMO_GUIDE.md) for all five demos and the full two-account walkthrough.

## Demonstrated in Studio

See [DEMO_RESULTS.md](DEMO_RESULTS.md) for the recorded run, deployment address and screenshots.

## Testing

`test_contract.py` contains 19 local tests using a simulated GenLayer runtime and authored AI answers. They check permissions, both hash consents, the lifecycle, quote checking (log and terms), validator disagreement, audit rejection, malformed AI output and retries, pay maths, appeals and demo isolation. They test the contract's behaviour, not the AI's judgement. See [VERIFICATION.md](VERIFICATION.md).

## Boundaries

- This records what is owed under the agreed terms. It moves no money and isn't legal advice or a replacement for an employment tribunal or ACAS.
- It checks the sign-in log it is given; it can't prove the log is genuine or complete.
- All data is public on-chain. Use staff IDs, not real names.
- Instructions hidden in inputs are treated as data. This reduces prompt injection but doesn't guarantee against it.
- Strict independent agreement means a genuinely borderline claim may fail to reach consensus and need retrying, or a clearer claim.
- Different addresses do not prove different people.

## Built with

- [GenLayer](https://docs.genlayer.com) Intelligent Contracts (Python, GenVM v0.2.16 runner)
- Developed with help from Claude
