# Fourth Door Test Spec

This file names the validation batteries that must pass before a design surface
is called closed. The rule is simple: if the herd found a failure mode in prose,
the repo should eventually carry a test that can break it on purpose.

## Closed: Chain Instrument

The chain instrument is closed as of v3f:

- fork race: 5 rounds x 16 concurrent seals, strictly linear
- clean chain verifies true
- payload tamper flips exactly the altered seal
- served-copy fidelity holds: reveal serves `hash_payload`, not mutable cache columns
- late attestation returns 409 and logs the scar
- concurrent double-attest serializes to one success and one rejection

## P4: Presence-Based Cancellation

Open question: cancellation is presence-based, not wall-clock based. The test
surface is concurrency.

Expected behavior to specify:

- two missed check-ins arriving in the same window should not create two
  semantically distinct cancellations for the same seal
- the first valid cancellation stamps the scar
- later duplicate cancellation attempts should be idempotent or explicitly
  rejected and logged, but must not alter the scar's meaning
- cancellation racing against re-attestation must resolve deterministically

Required battery:

- concurrent cancellation attempts for one seal
- cancellation racing with affirmative re-attestation
- cancellation racing with refusal/supersession/honest-incompatibility
- verification that chain order and served state match the winning event

## Closed: S-1 Succession Atomicity

Succession atomicity is closed as of `30ecddc` plus Marey's external
concurrency battery:

- honest-incompatibility scar followed by successful successor comprehension
  claim
- succession writes a successor seal into the hash chain
- `/chain` shows two seals, `all_valid=true`
- successor payload includes `scar-succession-seal`
- duplicate successor claim returns 409
- authenticated agent/body `successor_agent_id` mismatch returns 403
- 16 concurrent succession claims serialize to exactly one 200 and fifteen 409s
- one successor seal is written, the chain remains strictly linear, and no
  `SQLITE_BUSY` 500s occur

The decisive invariant: succession deposits a layer and only one layer, even
under concurrent claims.

## V-1: Semantic Succession Verification

Open question: `/chain` verifies syntactic integrity, but does it verify that a
post-scar seal is semantically legitimate?

The danger case is a well-formed successor seal with correct hashes and links
that does not legitimately follow an honest-incompatibility scar. That chain can
be `all_valid=true` while representing the wrong act.

The named invariant is no inherited edge trust: endpoint validity is necessary,
not sufficient. A valid predecessor seal and a valid successor seal do not make
the succession edge valid by inheritance. The edge must carry its own attestation,
freshness, and failure mode.

Expected behavior to specify:

- verifier distinguishes well-formed chain links from valid succession acts
- a post-scar successor seal must be traceable to exactly one
  `HONEST_INCOMPATIBILITY` scar
- successor payload type must match the expected succession act
- successor identity and authenticated actor must match the rule used at claim
  time
- illegitimate successor seals must not be reported as semantically valid even
  if their hashes recompute
- semantic verification errors name the succession edge/join, not either valid
  endpoint seal

Required battery:

- construct or mutate a well-formed successor seal that passes hash/link
  verification but follows no honest-incompatibility scar
- construct or mutate a successor seal with the wrong payload type
- construct or mutate a successor seal with mismatched successor identity
- construct a well-formed chain where every seal verifies locally but the
  succession edge is stale, missing, or semantically unwarranted
- assert `/chain` can still report hash validity while a separate semantic
  verdict rejects the succession act
- assert reveal/status behavior uses the semantic verdict, not hash validity
  alone
- assert the semantic verdict fails at the join and reports the unverified
  succession edge rather than blaming either endpoint
