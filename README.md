# ulc-fingerprint

A layered classifier that labels a MIFARE Ultralight C card as genuine NXP or a
known counterfeit (Giantec GT23SC4489 / ULCG, Feiju FJ8010, USCUID-UL) from a
fingerprint capture, and prints the evidence behind the verdict.

It builds on the research in "BREAKMEIFYOUCAN!": Exploiting Keyspace Reduction
and Relay Attacks in 3DES and AES-protected NFC Technologies
(https://eprint.iacr.org/2026/100) and the fingerprint data in its resource
repo (https://github.com/zc-public/breakme-resources, GPLv3).

## Why this exists

The paper gives per-card fingerprint dumps and a live probe (`fingerprint_ulc.py`)
that talks to a Proxmark3, but no tool that takes a capture and says what the
card is. The methodology notes even leave a `TODO: fingerprint in the table`.
This fills that gap and makes one point sharp:

**Frame-delay timing (FDT) alone catches only two of the four counterfeits.**

| Card | FDT AF (bad key) | Caught by timing? | What catches it |
|------|------------------|-------------------|-----------------|
| Genuine NXP ULC | ~842 us | n/a | broad command map, TRNG nonces |
| Giantec GT23SC4489 (ULCG) | ~78 us | yes, loud | FDT (LFSR bails ~10x early) |
| USCUID-UL v1 | ~3645 us | yes, loud | FDT (several times slow) |
| Feiju FJ8010 | ~843 us | **no, looks genuine** | command map (ACKs only 0xA0) |
| USCUID-UL v2 | ~842 us | **no, looks genuine** | command map / PRNG nonce test |

So the classifier runs the checks in order of cost and falls through:

1. **FDT bucket** on the bad-key AF response. Flags ULCG and USCUID-UL v1 outright.
2. **Command-response map.** Genuine NXP ACKs almost the whole command range
   (~200 commands return `00` to `XX00+CRC`). ULCG and FJ8010 ACK a tiny set,
   often just `0xA0`. USCUID-UL ACKs broadly but with a `0x50-0x5F` gap
   (`0x60-0xA1`, not `0x51-0xA1`). This is what catches the timing-genuine fakes.
3. **PRNG quality.** Repeated or wrong-CRC-but-valid RndB means a weak LFSR, not
   the genuine TRNG. Needs a nonce capture, so it is the last layer.

Each verdict carries its evidence and a confidence, and a timing-only capture of
a genuine-looking card is reported as `suspect` with a caveat rather than
false-cleared.

## Usage

```
python3 ulc_classify.py capture.txt           # human-readable verdict + evidence
python3 ulc_classify.py capture.txt --json     # machine-readable
cat capture.txt | python3 ulc_classify.py -    # stdin
python3 ulc_classify.py capture.txt -vv        # debug trace to stderr
```

A capture is the text output of the BREAKMEIFYOUCAN `fingerprint_ulc.py` probe,
or any capture with the same lines (`FDT to ...`, `Cmd **00=00: ...`,
`Answer to RATS:`, `Cmd 1a00: ...`). See `CAPTURE.md` for how to produce one
with a Proxmark3.

## Validation

`fixtures/` holds the authors' own labelled reference captures. The test suite
classifies each one and asserts it matches its label, so the classifier is
pinned to the paper's ground truth.

```
python3 -m pytest tests/ -q
```

## Status and contribution path

This is staged as a contribution to `breakme-resources` (GPLv3), which is why it
is GPLv3 and uses their captures as fixtures. The natural follow-on is upstream
Proxmark3: `hf mfu info` already prints a `Fingerprint: n/a` stub, and this
decision logic is what would fill it. That one needs live hardware to validate.

## Attribution

Reference captures and the fingerprint methodology are from the
BREAKMEIFYOUCAN authors (Nye, Teuwen, Messmer, Mauch, Clark, Li, Weiss,
Voeltner), eprint.iacr.org/2026/100 and github.com/zc-public/breakme-resources.
Licensed GPLv3, matching the source repository.
