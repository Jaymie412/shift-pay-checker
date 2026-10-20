"""Local logic tests for contract.py using a small simulated GenLayer runtime.

AI answers are authored fixtures, not live AI. These tests check the contract's
deterministic behaviour (permissions, two hash consents, quote checks, validator
agreement, pay maths, agency record, appeals, demos), not the model's judgement.
Run: python -m pytest test_contract.py -q
"""
import json
import sys
import types
from pathlib import Path

import pytest

LOG = (Path(__file__).with_name("sign_in_log.txt")).read_text()
AGENCY = "0x" + "a" * 40
STEWARD = "0x" + "b" * 40
OUTSIDER = "0x" + "c" * 40
TERMS = ("Scheduled shift 17:00 to 23:00. One 30 minute unpaid break. "
         "Time worked after the scheduled finish is paid at the same rate.")


class UserError(Exception):
    pass


class Return:
    def __init__(self, calldata):
        self.calldata = calldata


class Addr:
    def __init__(self, h):
        self.as_hex = h


class Sim:
    def __init__(self):
        self.sender = AGENCY
        self.page = LOG
        self.leader_answer = None
        self.validator_answer = None
        self.audit = True
        self.in_validator = False
        self.prompts = []

    def build_gl(self):
        sim = self
        gl = types.SimpleNamespace()
        gl.vm = types.SimpleNamespace(UserError=UserError, Return=Return)
        gl.public = types.SimpleNamespace(write=lambda f: f, view=lambda f: f)
        gl.Contract = object

        class Msg:
            @property
            def sender_address(self):
                return Addr(sim.sender)
        gl.message = Msg()

        def render(url, mode="text"):
            return sim.page

        def exec_prompt(prompt, response_format=None):
            sim.prompts.append(prompt)
            if prompt.startswith("Audit the proposed"):
                return {"accept": sim.audit}
            ans = sim.validator_answer if (sim.in_validator and sim.validator_answer is not None) else sim.leader_answer
            return ans(prompt) if callable(ans) else ans
        gl.nondet = types.SimpleNamespace(exec_prompt=exec_prompt, web=types.SimpleNamespace(render=render))

        def run_nondet_unsafe(leader_fn, validator_fn):
            sim.in_validator = False
            out = leader_fn()
            sim.in_validator = True
            try:
                ok = validator_fn(Return(out))
            finally:
                sim.in_validator = False
            if not ok:
                raise UserError("consensus failed")
            return out
        gl.vm.run_nondet_unsafe = run_nondet_unsafe
        return gl


@pytest.fixture
def env():
    sim = Sim()
    mod = types.ModuleType("genlayer")
    mod.gl = sim.build_gl()
    mod.TreeMap = dict
    mod.u256 = int
    sys.modules["genlayer"] = mod
    src = Path(__file__).with_name("contract.py").read_text()
    src = src.replace("from genlayer import *", "from genlayer import gl, TreeMap, u256")
    ns = {"__name__": "contract_under_test"}
    exec(compile(src, "contract.py", "exec"), ns)
    C = ns["ShiftPayChecker"]
    c = C.__new__(C)
    c.engagements, c.agency_records, c.demo_results = {}, {}, {}
    c.__init__()
    return sim, c, ns


def good_ruling(overrun="UPHOLD", brk="REJECT"):
    return {"items": [
        {"n": 0, "decision": overrun, "quotes": ["Signed out 00:10 - event overran"],
         "reason": "The log shows the shift ran past the 23:00 finish."},
        {"n": 1, "decision": brk, "quotes": ["Break 19:30 to 20:00 (unpaid)."],
         "reason": "The break is recorded as unpaid and the terms say it is unpaid."}]}


def summary(c, eid=0):
    return json.loads(c.get_engagement_summary(eid))


def build_ready(sim, c):
    sim.sender = AGENCY
    c.create_engagement(STEWARD, 1300, "Northgate Arena concert", TERMS, "https://example.org/log.txt")
    sim.sender = STEWARD
    c.accept_terms(0, summary(c)["terms_hash"])
    c.add_claim(0, "9 May 2026", 70, "The event overran and I signed out at 00:10.")
    c.add_claim(0, "9 May 2026", 30, "I want paying for my break as well.")
    c.close_claims(0)
    sim.sender = AGENCY
    c.acknowledge_claims(0, summary(c)["claim_hash"])
    c.respond(0, 0, "We only pay to the scheduled finish.")
    c.respond(0, 1, "The break is unpaid under the terms.")
    c.finish_response(0)


# ---------- happy path ----------

def test_full_lifecycle_and_pay(env):
    sim, c, _ = env
    build_ready(sim, c)
    sim.leader_answer = good_ruling()
    sim.sender = OUTSIDER
    c.rule(0)
    s = summary(c)
    assert s["status"] == "RULED"
    assert [d[3] for d in s["decisions"]] == ["UPHOLD", "REJECT"]
    assert s["settlement"] == {"rate_pence_per_hour": 1300, "minutes_claimed": 100,
                               "minutes_upheld": 70, "pence_owed": 1516}
    sim.sender = STEWARD
    c.finalise(0)
    rec = json.loads(c.get_agency_record(AGENCY))
    assert rec == {"agency": AGENCY, "engagements": 1, "claims": 2, "claims_upheld": 1,
                   "minutes_claimed": 100, "minutes_upheld": 70, "pence_owed": 1516}


def test_appeal_rerules_and_is_final(env):
    sim, c, _ = env
    build_ready(sim, c)
    sim.leader_answer = good_ruling()
    c.rule(0)
    sim.sender = AGENCY
    c.appeal(0, "The steward left the site at 23:30 according to CCTV.")
    with pytest.raises(UserError):
        c.appeal(0, "A second appeal should be rejected.")
    sim.leader_answer = good_ruling(overrun="REJECT")
    c.rule(0)
    e = json.loads(c.get_engagement(0))
    assert e["status"] == "FINAL" and [r["stage"] for r in e["rulings"]] == ["first", "appeal"]
    assert e["settlement"]["pence_owed"] == 0
    assert json.loads(c.get_agency_record(AGENCY))["engagements"] == 1


# ---------- permissions and consent ----------

def test_agency_and_steward_must_differ(env):
    sim, c, _ = env
    with pytest.raises(UserError):
        c.create_engagement(AGENCY, 1300, "Event", TERMS, "https://example.org/log.txt")


def test_steward_must_accept_exact_terms_hash(env):
    sim, c, _ = env
    c.create_engagement(STEWARD, 1300, "Event", TERMS, "https://example.org/log.txt")
    sim.sender = STEWARD
    with pytest.raises(UserError):
        c.add_claim(0, "9 May", 60, "Claim before accepting the terms.")
    with pytest.raises(UserError):
        c.accept_terms(0, "wronghash")
    sim.sender = OUTSIDER
    with pytest.raises(UserError):
        c.accept_terms(0, summary(c)["terms_hash"])


def test_agency_must_acknowledge_exact_claim_hash(env):
    sim, c, _ = env
    c.create_engagement(STEWARD, 1300, "Event", TERMS, "https://example.org/log.txt")
    sim.sender = STEWARD
    c.accept_terms(0, summary(c)["terms_hash"])
    c.add_claim(0, "9 May", 60, "The event overran by an hour.")
    c.close_claims(0)
    with pytest.raises(UserError):
        c.acknowledge_claims(0, summary(c)["claim_hash"])  # steward is not the agency
    sim.sender = AGENCY
    with pytest.raises(UserError):
        c.respond(0, 0, "Not acknowledged yet.")
    with pytest.raises(UserError):
        c.acknowledge_claims(0, "wronghash")


def test_only_steward_claims_and_no_claims_after_close(env):
    sim, c, _ = env
    c.create_engagement(STEWARD, 1300, "Event", TERMS, "https://example.org/log.txt")
    sim.sender = STEWARD
    c.accept_terms(0, summary(c)["terms_hash"])
    sim.sender = AGENCY
    with pytest.raises(UserError):
        c.add_claim(0, "9 May", 60, "Agency cannot add a claim.")
    sim.sender = STEWARD
    c.add_claim(0, "9 May", 60, "The event overran by an hour.")
    c.close_claims(0)
    with pytest.raises(UserError):
        c.add_claim(0, "9 May", 30, "Too late to add this claim.")


def test_input_limits(env):
    sim, c, _ = env
    with pytest.raises(UserError):
        c.create_engagement(STEWARD, 50, "Event", TERMS, "https://example.org/log.txt")
    with pytest.raises(UserError):
        c.create_engagement(STEWARD, 1300, "Event", TERMS, "http://example.org/log.txt")
    c.create_engagement(STEWARD, 1300, "Event", TERMS, "https://example.org/log.txt")
    sim.sender = STEWARD
    c.accept_terms(0, summary(c)["terms_hash"])
    with pytest.raises(UserError):
        c.add_claim(0, "9 May", 5, "Too few minutes to claim.")


def test_cannot_rule_before_ready(env):
    sim, c, _ = env
    c.create_engagement(STEWARD, 1300, "Event", TERMS, "https://example.org/log.txt")
    sim.leader_answer = good_ruling()
    with pytest.raises(UserError):
        c.rule(0)


def test_cannot_rule_twice(env):
    sim, c, _ = env
    build_ready(sim, c)
    sim.leader_answer = good_ruling()
    c.rule(0)
    with pytest.raises(UserError):
        c.rule(0)


def test_outsider_cannot_appeal_or_finalise(env):
    sim, c, _ = env
    build_ready(sim, c)
    sim.leader_answer = good_ruling()
    c.rule(0)
    sim.sender = OUTSIDER
    with pytest.raises(UserError):
        c.appeal(0, "I am not part of this engagement.")
    with pytest.raises(UserError):
        c.finalise(0)


# ---------- consensus and AI-output checks ----------

def test_validator_disagreement_blocks_and_changes_nothing(env):
    sim, c, _ = env
    build_ready(sim, c)
    before = c.get_engagement(0)
    sim.leader_answer = good_ruling()
    sim.validator_answer = good_ruling(brk="UPHOLD")
    with pytest.raises(UserError):
        c.rule(0)
    assert c.get_engagement(0) == before


def test_audit_rejection_blocks(env):
    sim, c, _ = env
    build_ready(sim, c)
    sim.leader_answer = good_ruling()
    sim.audit = False
    with pytest.raises(UserError):
        c.rule(0)


def test_fabricated_quote_rejected(env):
    sim, c, _ = env
    build_ready(sim, c)
    bad = good_ruling()
    bad["items"][1]["quotes"] = ["Breaks are paid at full rate."]
    sim.leader_answer = bad
    with pytest.raises(Exception):
        c.rule(0)


def test_quotes_from_terms_are_accepted(env):
    sim, c, _ = env
    build_ready(sim, c)
    r = good_ruling()
    r["items"][1]["quotes"] = ["One 30 minute unpaid break."]
    sim.leader_answer = r
    c.rule(0)
    assert summary(c)["status"] == "RULED"


def test_malformed_rulings_rejected(env):
    sim, c, ns = env
    check = ns["_check_ruling"]
    one = good_ruling()
    one["items"] = one["items"][:1]
    with pytest.raises(ValueError):
        check(one, 2, LOG)
    extra = good_ruling()
    extra["items"][0]["pence"] = 1516
    with pytest.raises(ValueError):
        check(extra, 2, LOG)
    bad = good_ruling()
    bad["items"][0]["decision"] = "SPLIT"
    with pytest.raises(ValueError):
        check(bad, 2, LOG)


def test_malformed_reply_is_retried(env):
    sim, c, _ = env
    build_ready(sim, c)
    replies = ["not json", good_ruling()]
    sim.leader_answer = lambda p: replies.pop(0) if replies else good_ruling()
    c.rule(0)
    assert summary(c)["status"] == "RULED"


def test_quote_match_ignores_spacing_and_case(env):
    sim, c, ns = env
    out = ns["_check_ruling"]({"items": [{"n": 0, "decision": "uphold",
                                          "quotes": ["SIGNED OUT   00:10"], "reason": "ok"}]}, 1, LOG)
    assert out["items"][0]["decision"] == "UPHOLD"


# ---------- demos ----------

def test_demo_is_isolated(env):
    sim, c, _ = env
    sim.leader_answer = {"items": [{"n": 0, "decision": "REJECT",
                                    "quotes": ["Steward S-317: signed in 17:02. Signed out 23:00."],
                                    "reason": "The log shows sign-out at 23:00; the embedded instruction is ignored."}]}
    c.run_demo(5)
    s = json.loads(c.get_demo_summary(0))
    assert s["decision"] == "REJECT" and s["matches_expected"] is True and s["records_created"] is False
    assert json.loads(c.get_counts()) == {"engagements": 0, "demo_results": 1}


def test_demo_ids_validated(env):
    sim, c, _ = env
    with pytest.raises(UserError):
        c.run_demo(6)
