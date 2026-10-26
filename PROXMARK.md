# Proxmark3 `hf mfu` PRNG patch

`proxmark3-hf-mfu-prng.patch` adds a generic weak-PRNG check to the Ultralight C
fingerprint in the Proxmark3 client (`client/src/cmdhfmfu.c`).

## What it adds and why

The existing `mfulc_fingerprint()` already identifies the known counterfeit
families (Lab401 DW, Feiju FJ8010, USCUID-UL v1/v2, Giantec GT23SC4489,
Hospitality) by their deterministic command and CRC tells, and returns as soon
as one matches. What it does not do is catch a weak-RNG clone that matches none
of those profiles.

This patch adds `mfulc_prng_test()` and calls it on the genuine-looking
fallthrough, right before the `likely MF0ICU2` verdict. It collects RndB nonces
with repeated `1A 00` auth starts and looks for a duplicate:

- Genuine NXP draws RndB from a hardware TRNG (2^64), so it never repeats across
  a realistic batch.
- Giantec/USCUID use a 16-bit LFSR whose wakeup-timing seed concentrates the
  observed pool to ~2^6.5, so a duplicate shows up within ~12 authentications.

A single collision is proof of a weak PRNG. So this is the catch-all backstop
for weak-RNG clones, including future variants, that evade the fixed profile
table. `MFULC_PRNG_SAMPLES` (40) and `MFULC_PRNG_CLEAR` (39) are tunable.

## Status: UNTESTED, needs a bench

This has not been compiled or run on hardware. It is written against the current
`cmdhfmfu.c` and reuses existing helpers (`ul_select`,
`ulc_requestAuthentication`, `DropField`), and the patch applies cleanly, but it
must be built and validated on a real card (one genuine ULC, one Giantec or
USCUID counterfeit) before it is PR-worthy.

## Apply and build

```
cd /path/to/proxmark3
patch -p1 < proxmark3-hf-mfu-prng.patch      # or: git apply proxmark3-hf-mfu-prng.patch
make client            # or the client-only target for your setup
```

## Test plan

1. Genuine NXP ULC: `hf mfu info` should end with
   `PRNG......... no RndB collision in 40 nonces, consistent with a genuine TRNG`.
2. Giantec/USCUID counterfeit: the family line should still fire first (early
   return). To exercise the PRNG path directly, test a weak-RNG card that the
   profile table does not match, or temporarily short-circuit the early returns;
   expect `PRNG......... weak: repeated RndB (...)`.
3. Confirm no regression in timing or output on `hf mfu info` for a genuine card
   (the 40-cycle loop adds ~1 to 2 seconds, only on genuine-looking cards).

Tune `MFULC_PRNG_SAMPLES` down if the added `info` time is unwelcome; 24 still
catches the concentrated LFSR ~95% of the time.
