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

## S-1: Succession End-To-End

Open question: succession must be atomic with respect to the chain. The danger
case is a successor claim that exists without a re-attestation.

Expected behavior to specify:

- a successor claim and its required re-attestation must either commit as one
  ordered chain transition or fail as one transition
- after process restart, a fresh reader must never see an ambiguous "live"
  succession claim that has no corresponding attestation
- if partial succession is represented at all, it must be legible as partial
  and terminal/retriable by explicit rule, not by reader guesswork
- a second succession attempt racing the first must resolve deterministically

Required battery:

- honest-incompatibility scar followed by successful successor comprehension
  claim and re-attestation
- fault injection: kill process between successor claim and re-attestation,
  restart, and assert the visible state is deterministic
- two concurrent successor claims against the same scar
- successor claim racing with cancellation/re-attestation attempts
- verification that reveal behavior remains blocked or enabled according to the
  final chain state, not transient intermediate state

