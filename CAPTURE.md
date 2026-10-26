# Capturing a fingerprint for the classifier

The classifier reads the text output of the BREAKMEIFYOUCAN `fingerprint_ulc.py`
probe. That probe drives a Proxmark3 through the `pm3` Python module and needs a
card on the antenna. The three things the classifier actually uses:

- **FDT lines** (`FDT to 1A00 ...`, `FDT to AF* (bad key) ...`, `... (def key) ...`)
- **Command map** (`Cmd **00=00: <ranges>`)
- **RndB samples / PRNG tells** (`Cmd 1a00: <hex>`, any `valid lfsr` / `wrong CRC` note)

## With the authors' probe (recommended)

From a checkout of `github.com/zc-public/breakme-resources`:

```
cd cards/ulc/analyses
# edit the flags at the top of fingerprint_ulc.py: FDT=True, FDT_AVG=True,
# CMD00=True, and set KEY to the system key if known (else leave default)
./fingerprint_ulc.py | tee /tmp/capture.txt
python3 /path/to/ulc_classify.py /tmp/capture.txt
```

## Minimal manual capture (Proxmark3 Easy, no probe)

If you only want the timing discriminator, the bad-key AF FDT is enough to flag
ULCG and USCUID-UL v1. In the `pm3` client:

```
hf 14a raw -sc 1A00                 # start auth, capture ek(RndB)
hf 14a raw -c AF 00000000000000000000000000000000   # bad-key response
trace list -t 14a --frame           # read FDT ticks off the AF* / NAK frames
```

Record the FDT to `1A00` and the FDT to the `AF*` response under a bad key, then
hand-write a capture file with lines the parser understands:

```
UID:             <uid hex>
ATQA anticol:    00 44
SAK anticol:     00
Answer to RATS:  None
FDT to 1A00 (bad key):  <ticks>
FDT to AF*  (bad key):  <ticks>
FDT to AF*  (def key):  <ticks>
```

Timing alone will not separate FJ8010 or USCUID-UL v2 from genuine NXP; for
those you need the command map (`Cmd **00=00:`) and ideally a nonce capture.
The classifier says so in its caveats rather than guessing.

## Nonce capture for the PRNG layer

ULCG and USCUID-UL use a 16-bit LFSR, so RndB repeats fast: over 50% chance of a
duplicate within 12 nonces. Capture a batch of `1A00` responses; if the same
RndB recurs, or the client flags a valid-LFSR-but-wrong-CRC reply, that is a
weak-PRNG tell no genuine NXP card shows.
