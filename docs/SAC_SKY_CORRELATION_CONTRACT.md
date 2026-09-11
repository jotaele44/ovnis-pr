# SAC / Skywatcher correlation contract for OVNIS

Status: **PROVISIONAL / INTERNAL**

OVNIS consumes Skywatcher sky-domain candidate artifacts; it does not independently promote SAC articles into case identities or conventional explanations.

## Frozen baseline

- Repository baseline: `d70adbb49b562717001834957f85fdba88365c36`
- Skywatcher baseline for this coordinated change: `0521581cae5d7a46b04450322682a81a03d47149`
- SAC canonical origin: `https://www.sociedadastronomia.com/`

## Boundary

Skywatcher owns physical sky reconstruction and candidate generation.
OVNIS owns case evidence adjudication.
The same SAC manifestation may support multiple candidate events and the same OVNIS case may retain multiple competing candidates. N:N is therefore permitted only when explicit and conserved; silent row multiplication is forbidden.

## Required candidate evidence

For each `case_id × sky_event_id` edge preserve:

- stable case identifier
- stable Skywatcher event identifier
- source manifestation identifiers
- time test
- location/visibility test
- azimuth test
- elevation test when available
- trajectory test
- duration test
- appearance test
- upstream identity test when available
- contradictions
- unresolved fields
- final bounded classification

## Final states

- `MATCHED` — all material available gates pass and no material contradiction remains.
- `PARTIAL` — some evidence agrees but at least one material gate is absent or indeterminate.
- `CONTRADICTED` — one or more material observations falsify the candidate.
- `UNRESOLVED` — evidence is insufficient or tied.

`MATCHED` means a candidate explanation is evidentially supported within the declared scope. It does not rewrite the historical case record and does not imply that every witness description or secondary report has been explained.

## Forbidden identity shortcuts

Never promote an explanation using only:

- name equality
- normalized-name equality
- time proximity
- spatial proximity
- category equality
- nearest candidate
- candidate count equality
- absence of another candidate

## Candidate-set preservation

Every run must retain the complete candidate set before ranking or adjudication. Tied top evidence remains `UNRESOLVED` or review-required. Deterministic ranking is not evidence.

## Arithmetic closure

For the declared case denominator:

`TOTAL_CASES = MATCHED_CASES + PARTIAL_CASES + CONTRADICTED_ONLY_CASES + UNRESOLVED_CASES + NO_ELIGIBLE_SKY_DATA_CASES`

Candidate-edge counts are tracked separately and must not be substituted for case counts.

## Regression requirements

Positive fixtures must include known astronomical/space events with deliberately compatible observation facts.
Negative fixtures must include deliberate false matches, including:

- correct time but wrong azimuth
- correct time and azimuth but incompatible motion
- correct category but wrong date
- nearby event outside visibility geometry
- multiple simultaneous plausible candidates with tied evidence

## Certification prohibition

`SAC SOURCE INTEGRATION CERTIFIED` and any claim that a complete OVNIS denominator has been cross-referenced are prohibited until Skywatcher closes its bounded SAC archive denominator, freezes source manifestations/hashes, and exports validated versioned sky-event artifacts consumed by OVNIS with zero unexplained material residue.