"""Regression tests: the classifier must reproduce the paper's ground truth on
every reference capture in fixtures/. These fixtures are the authors' own
labelled probes, so a correct classifier labels each one as its filename says.
"""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from ulc_classify import (  # noqa: E402
    Verdict, analyze_nonces, classify, parse_fingerprint,
)

FIX = pathlib.Path(__file__).resolve().parent.parent / "fixtures"


def _run(name: str):
    fp = parse_fingerprint((FIX / name).read_text())
    return fp, classify(fp)


# (fixture, expected verdict, expected minimum confidence)
CASES = [
    ("nxp_genuine.txt", Verdict.GENUINE, "medium"),
    ("ulcg_giantec.txt", Verdict.ULCG, "high"),
    ("fj8010_feiju.txt", Verdict.FJ8010, "high"),
    ("uscuid_ul_v1.txt", Verdict.USCUID, "high"),
]

CONF_RANK = {"low": 0, "medium": 1, "high": 2}


@pytest.mark.parametrize("name,expected,min_conf", CASES)
def test_reference_classification(name, expected, min_conf):
    fp, res = _run(name)
    assert res.verdict == expected, f"{name}: got {res.verdict} ({res.evidence})"
    assert CONF_RANK[res.confidence] >= CONF_RANK[min_conf], \
        f"{name}: confidence {res.confidence} below {min_conf}"


def test_fdt_alone_would_miss_fj8010():
    """The whole point: FJ8010 has genuine-looking timing. Prove the FDT bucket
    matches NXP, so timing alone would pass it, and the command map is what
    flags it."""
    from ulc_classify import FDT_AF_BAD_NXP, FDT_TOL
    fp, res = _run("fj8010_feiju.txt")
    assert abs(fp.fdt_af_badkey - FDT_AF_BAD_NXP) <= FDT_TOL, \
        "FJ8010 FDT should sit in the genuine bucket"
    assert res.verdict == Verdict.FJ8010
    assert any("command map" in e for e in res.evidence), \
        "FJ8010 must be caught by the command map, not timing"


def test_uscuid_v2_timing_genuine_is_flagged_not_cleared():
    """USCUID-UL v2 looks genuine by timing and the fixture has no command map
    or nonce data. The classifier must not call it genuine on timing alone; it
    should say GENUINE only with a caveat, or stay short of high confidence."""
    fp, res = _run("uscuid_ul_v2.txt")
    # v2 fixture is timing-only; a safe classifier cannot confirm genuineness.
    assert res.confidence != "high"
    if res.verdict == Verdict.GENUINE:
        assert res.caveats, "timing-only genuine verdict must carry a caveat"


def test_partial_capture_is_inconclusive_not_crash():
    fp = parse_fingerprint("UID: 0400000000000080\nSAK anticol: 00\n")
    res = classify(fp)
    assert res.verdict in (Verdict.INCONCLUSIVE, Verdict.GENUINE, Verdict.SUSPECT)
    assert res.confidence in ("low", "medium")


def test_range_expansion():
    from ulc_classify import _expand_ranges
    got = _expand_ranges("00-02,10,1b-1c")
    assert got == {0x00, 0x01, 0x02, 0x10, 0x1b, 0x1c}


# --- nonce collision analysis -----------------------------------------------

def test_nonces_lfsr_batch_flagged():
    from ulc_classify import _extract_nonces
    text = (FIX / "nonces_ulcg.txt").read_text()
    rep = analyze_nonces(_extract_nonces(text))
    assert rep.duplicates > 0
    assert rep.verdict == Verdict.SUSPECT and rep.confidence == "high"
    # effective pool should land near the paper's ~2^6.5, not the 2^16 state space
    assert rep.est_pool is not None and 16 < rep.est_pool < 512


def test_nonces_genuine_batch_cleared():
    from ulc_classify import _extract_nonces
    text = (FIX / "nonces_genuine.txt").read_text()
    rep = analyze_nonces(_extract_nonces(text))
    assert rep.duplicates == 0
    assert rep.verdict == Verdict.GENUINE


def test_single_duplicate_is_conclusive():
    # one repeat is enough: a 2^64 TRNG colliding is ~0
    rep = analyze_nonces(["AABBCCDDEEFF0011", "1122334455667788", "AABBCCDDEEFF0011"])
    assert rep.duplicates == 1
    assert rep.first_collision_at == 3
    assert rep.p_genuine_would_dup < 1e-30
    assert rep.verdict == Verdict.SUSPECT


def test_too_few_nonces_inconclusive():
    rep = analyze_nonces(["AABBCCDDEEFF0011", "1122334455667788"])
    assert rep.duplicates == 0
    assert rep.verdict == Verdict.INCONCLUSIVE


def test_nonce_normalization_strips_af_and_crc():
    from ulc_classify import _normalize_nonce
    assert _normalize_nonce("AF BC8FCFBE5821FFBC [6355]") == "BC8FCFBE5821FFBC"
    # AF-prefixed and bare forms of the same RndB collide within a batch
    rep = analyze_nonces(["AFBC8FCFBE5821FFBC[6355]", "BC8FCFBE5821FFBC"])
    assert rep.duplicates == 1
