# Shift Pay Checker demo results

- Date:
- Contract address:
- Agency account (A):
- Steward account (B):

## Part A: demos

| case_id | result_id | Expected | Actual | pence_owed | matches_expected | records_created | Screenshot |
|---:|---:|---|---|---:|---|---|---|
| 1 | 0 | UPHOLD | | | | | |
| 2 | 1 | REJECT | | | | | |
| 3 | 2 | REJECT | | | | | |
| 4 | 3 | UPHOLD | | | | | |
| 5 | 4 | REJECT | | | | | |

## Part B: real claim

| Step | Account | Method | Result | Screenshot |
|---|---|---|---|---|
| 1-2 | A | create_engagement | PROPOSED, terms_hash | |
| 3 | B | accept_terms | ACTIVE | |
| 4-6 | B | add_claim x2, close_claims | AWAITING_AGENCY, claim_hash | |
| 7-9 | A | acknowledge_claims, respond x2, finish_response | READY | |
| 10 | any | rule | RULED | |
| 11 | B | finalise | FINAL | |

## Notes

Record anything that failed or needed retrying, and why.
