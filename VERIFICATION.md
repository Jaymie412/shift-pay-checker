# Shift Pay Checker verification

Contract file: `contract.py`, version `shift-pay-0.1`.

## Local checks completed

- Python syntax compilation succeeded.
- Every GenLayer SDK call the contract uses (`gl.vm.run_nondet_unsafe`, `gl.vm.Return`, `gl.nondet.exec_prompt`, `gl.nondet.web.render`, `gl.vm.UserError`, `gl.message.sender_address`) is used by my Deposit Dispute Court contract (accepted), which ran end to end on GenLayer Studio with the same `py-genlayer` runner.
- `test_contract.py`: **19 tests passed** against a simulated GenLayer runtime.

The official `genlayer-test` package couldn't be installed in the environment used, so the tests use a small simulated runtime instead. All AI answers in the tests are authored fixtures. They check the contract's deterministic behaviour, not the AI's judgement.

## What the tests cover

1. Full lifecycle and pay maths (£13.00/hour, 70 of 100 minutes upheld, 1516 pence owed) and the agency record.
2. Appeal: one per engagement, re-ruling, both rulings kept, final status, agency record counted once.
3. Agency and steward must be different addresses.
4. The steward must accept the exact `terms_hash` before claiming; wrong hashes and outsiders are rejected.
5. The agency must acknowledge the exact `claim_hash` before responding.
6. Only the steward can add claims; no claims after closing.
7. Input limits: rate, https-only log link, claim minutes.
8. Rulings can't happen before the claims are ready, or twice.
9. Outsiders can't appeal or finalise.
10. A validator reaching a different decision blocks the ruling and leaves the engagement unchanged.
11. A failed audit blocks the ruling.
12. Fabricated quotes are rejected; quotes from the agreed terms are accepted.
13. Missing items, extra fields and unknown decisions are rejected.
14. A malformed AI reply is asked again instead of failing the transaction.
15. Quote matching tolerates spacing and capital letters only.
16. Demos are isolated: no engagements or agency records are created.

## Live Studio evidence

Recorded in GenLayer Studio on 20 October 2026 at `0x192df877642aFdC0204Af92c45492c096fB25ef8`. Full details and screenshots are in [DEMO_RESULTS.md](DEMO_RESULTS.md).

- All 5 isolated demos matched their expected decision, including the prompt-injection case, and created no records.
- A real two-account claim ran end to end: terms set → steward accepted the exact terms hash → 2 claims → closed (claim hash) → agency acknowledged the exact claim hash → responses → READY → RULED (accepted by consensus on the first attempt) → FINAL.
- Ruling: overrun UPHOLD, break REJECT; 70 of 100 minutes upheld; 1516 pence owed. Agency record updated by code.
