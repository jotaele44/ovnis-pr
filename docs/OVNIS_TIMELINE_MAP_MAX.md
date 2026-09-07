# OVNIS-PR Timeline + Map MAX

Status: IMPLEMENTATION SPEC
Scope: public OVNIS-PR product surface + research GIS surface over the existing corpus producer
Baseline branch: `main`
Reference UX: ufotimeline.com, bounded observable audit snapshot 2026-09-07

## 1. Goal

Turn the existing OVNIS-PR corpus producer/dashboard into a Puerto Rico-focused public research product with a synchronized Timeline + Map as co-equal primary views, without duplicating federation authority already owned by Spiderweb, Skywatcher, AguaYLuz, MoneySweep, or TheHub.

Certification target is corpus/product integrity, not validation of extraordinary interpretations.

## 2. Current repo facts to preserve

The current repo already provides:

- React/Vite dashboard.
- FastAPI read-only backend.
- MapLibre GL sighting map.
- Git-native master/candidate JSONL ledgers.
- release GeoJSON/CSV generation.
- federation/HAF/admin-boundary gates.
- candidate/FOIA intake workflows.
- desktop/offline packaging.
- GUI capability audit and parity gates.

Do not replace passed artifacts unnecessarily. Extend compatibly.

## 3. Authority boundary

| Domain | Canonical authority | OVNIS-PR role |
|---|---|---|
| UAP/USO event interpretation | OVNIS-PR | producer + public presentation |
| Canonical geometry | Spiderweb-PR | bind foreign geometry IDs; do not silently redefine |
| Aviation telemetry | Skywatcher-PR | consume bounded aircraft/track bindings |
| Ocean/weather/hydrology | AguaYLuz-PR | consume environmental context |
| Company/procurement context | MoneySweep-PR | consume entity/award bindings |
| Cross-repo provenance/discovery | TheHub | federation control/query plane |

Invariant: foreign source identity remains foreign source identity.

## 4. Public information architecture

Primary navigation:

1. Timeline
2. Map
3. Cases
4. Documents
5. People
6. Places
7. Investigations
8. FOIA / Archives
9. Methodology

Timeline and Map MUST share one filter/selection state.

### Public Timeline

Required:

- year/date navigation
- decade range
- category filters
- evidence/source filters
- compact event cards
- deep links
- bilingual display
- source badges
- precision-aware date rendering
- map synchronization

### Public Map

Required:

- MapLibre-based rendering
- exact point / approximate point / locality / uncertainty polygon / track semantics
- clustering
- municipality filter
- category filter
- date-range filter
- evidence/source filter
- click case -> synchronized timeline/card selection
- deep-linked viewport/filter/event state
- mobile-safe card/map interaction

The public map MUST NOT expose arbitrary federation internals or privileged investigation tooling.

## 5. Research GIS surface

Research mode may expose:

- temporal playback
- bbox/radius discovery
- point-in-polygon
- topology states
- distance measurement
- uncertainty geometry
- reconstructed tracks
- historic layer switching
- source/witness/sensor positions
- competing reconstructions
- falsified candidate geometries
- federation context overlays through bounded bindings/services

Final spatial states:

`FULLY_WITHIN | PARTIAL | TOUCH_ONLY | OUTSIDE | NULL_EMPTY | UNRESOLVED`

Proximity, nearest-neighbor, buffers, fuzzy search, and bbox search are discovery evidence unless independently authoritative.

## 6. Canonical decomposition

Do not continue treating one denormalized case row as the only semantic object.

Required domain objects:

- `event`
- `observation`
- `claim`
- `source`
- `source_manifestation`
- `entity`
- `event_entity_binding`
- `location`
- `geometry_binding`
- `media`
- `foia_case`
- `investigation`
- `candidate_explanation`
- `contradiction`
- `citation`

Core invariant:

`EVENT != OBSERVATION != CLAIM != SOURCE != SOURCE_MANIFESTATION`

Multiple articles about one event MUST NOT become multiple events solely because the source manifestations differ.

## 7. Identity model

Permit:

`1:1 | 1:N | N:1 | N:N | 0:1 | UNRESOLVED`

Never prove identity using only:

- name
- normalized name
- equal counts
- nearest match
- proximity
- same category
- source absence

Preserve full candidate sets. Tied top evidence => `REVIEW/UNRESOLVED`.

## 8. Temporal model

Required fields:

- `date_start`
- `date_end`
- `date_precision`
- `time_start`
- `time_end`
- `time_precision`
- `timezone`
- `timezone_confidence`

Allowed precision classes should include at least:

`EXACT_SECOND | EXACT_MINUTE | APPROXIMATE_TIME | DATE_ONLY | MONTH_ONLY | YEAR_ONLY | DATE_RANGE | UNKNOWN`

Never fabricate precision from display needs.

## 9. Geometry model

Required geometry roles:

- `EXACT_POINT`
- `APPROXIMATE_POINT`
- `LOCALITY_CENTROID`
- `UNCERTAINTY_CIRCLE`
- `UNCERTAINTY_POLYGON`
- `OBSERVATION_LINE`
- `RECONSTRUCTED_TRACK`
- `SOURCE_NATIVE_GEOMETRY`
- `NULL_GEOMETRY`

Required provenance:

- source CRS
- canonical CRS
- geometry type
- Z/M preservation/loss
- precision class
- uncertainty radius/metadata
- source ID
- source manifestation ID
- derivation method/version
- geometry status

A locality centroid MUST NOT render as an exact sighting point.

## 10. Raw / normalized / canonical

Preserve raw strings exactly, including accents, typos, spacing, OCR defects, and historical vocabulary.

Keep separate:

- `RAW`
- `NORMALIZED`
- `CANONICAL`

Normalization alone is never identity proof.

## 11. Evidence and certification states

Use existing certification vocabulary consistently:

`PASS | FAIL | OPEN | BLOCKED | PROVISIONAL | AUDIT_ONLY | NONCANONICAL | CANDIDATE_NOT_IDENTITY | UNRESOLVED | SUPERSEDED`

Apply state independently to dimensions such as:

- event existence
- date/time
- location identity
- witness identity
- platform identity
- source authenticity
- document provenance
- sensor interpretation
- object identity
- explanation

A well-documented report does not prove the reported object's identity.

## 12. Contradictions

Preserve conflicting observations. Required contradiction classes should include:

`BYTE | SCHEMA | TIME | DATE | LOCATION | GEOMETRY | NAME | COUNT | CLASS | IDENTITY | SOURCE | SENSOR | DIRECTION | ALTITUDE | DURATION | OBJECT_COUNT`

Adjudication must preserve displaced results as `SUPERSEDED` when appropriate.

## 13. Falsification ledger

Candidate explanations must remain stored after rejection.

Minimum fields:

- hypothesis/candidate ID
- event ID
- candidate explanation
- supporting evidence refs
- contradicting evidence refs
- test method/version
- result state

Rejected candidate != deleted candidate.

## 14. Source manifestations and provenance

Freeze where possible:

- source
- canonical/retrieval URL
- retrieval UTC
- source publication/update date
- page/offset/query when relevant
- raw bytes where legally/permissibly stored
- SHA-256
- schema/parser/OCR version
- archive location

Different hashes prove byte difference only.

## 15. Bilingual contract

Store editorial bilingual fields separately, for example:

- `canonical_title_es`
- `canonical_title_en`
- `description_editorial_es`
- `description_editorial_en`

Never overwrite raw source-language strings.

## 16. Public taxonomy vs analytical taxonomy

Public categories may include:

- Sightings
- Famous Cases
- Documents
- Government Records
- News
- Photos & Video
- People
- Places
- Investigations
- FOIA Releases
- Historical Context

Analytical classes remain separate, e.g.:

- VISUAL
- RADAR
- SONAR
- ELECTRO_OPTICAL
- INFRARED
- ACOUSTIC
- MULTISENSOR
- AVIATION
- MARITIME
- SUBSURFACE
- PHOTO
- VIDEO
- DOCUMENTARY_ONLY
- TESTIMONY_ONLY

Public taxonomy != canonical analytical identity.

## 17. Spatial scope

Represent scope independently from discovery radius:

- PR_LAND
- PR_INTERNAL_WATERS
- PR_TERRITORIAL_SEA
- PR_EEZ
- PUERTO_RICO_TRENCH
- RESEARCH_BUFFER
- OUTSIDE
- UNRESOLVED

A configured research buffer MUST NOT be presented as a jurisdictional boundary.

## 18. Search/query contract

Simple search remains available.

Advanced filters should support:

- date/year/range
- event class
- source family/agency
- municipality/location
- evidence tier/state
- primary-source-only
- witness/entity
- military unit/facility
- aircraft/vessel
- FOIA identifier
- archive/document ID
- sensor
- object morphology
- duration
- bearing/altitude when present
- offshore/terrestrial scope
- contradiction state
- unresolved state

## 19. Deep-link state

Meaningful public/research state MUST be reproducible from the URL, including:

- active surface (`timeline|map`)
- filters
- selected event
- map viewport/bbox
- time range

Reload/back/forward MUST preserve state deterministically.

## 20. Mobile requirements

- `Map` and `Timeline` are direct primary tabs.
- Map selection opens a bottom/side card without losing filter state.
- Swiping/next-prev through visible filtered cases updates the map.
- No hidden desktop-only information required to understand evidence state.

## 21. Migration strategy

Do not hand-reenter the corpus.

Order:

1. Freeze current source/master/release manifestations.
2. Record counts/hashes/schema versions.
3. Add normalized decomposition tables/ledgers without deleting the legacy master row format.
4. Build deterministic legacy -> decomposed migration.
5. Produce reconciliation reports.
6. Adjudicate duplicate/identity/temporal/spatial residue.
7. Add API v2 over decomposed model.
8. Keep API v1 compatibility until parity is proven.
9. Add synchronized Timeline + Map UI.
10. Add Research GIS only after public state and authority boundaries pass.
11. Freeze migration receipt and release manifestations.

## 22. Required arithmetic/invariants

At minimum:

`source_count = retained + excluded + unresolved`

`input_cases = migrated + deliberately_excluded + unresolved`

Assert:

- stable-ID uniqueness
- required fields
- allowed enums/types
- valid coordinates/geometries
- CRS preservation/loss accounting
- no unintended row loss
- no unintended row multiplication
- no silent M:N expansion
- source/event separation
- unresolved candidate retention
- raw-string preservation
- foreign-ID referential validity
- deterministic ordering/serialization for comparable aggregate hashes

Unexplained mismatch => FAIL CLOSED.

## 23. Positive regression gates

- known title -> expected event
- historical alias -> expected candidate set
- known exact coordinate -> correct geometry role
- timeline selection -> correct map geometry
- map selection -> correct timeline/case selection
- source -> correct event bindings
- event -> complete source set
- URL reload -> identical public state

## 24. Negative regression gates

- same-name events do not merge by name alone
- same-date events do not merge by date alone
- nearby events do not merge by proximity alone
- multiple source manifestations do not multiply one event
- approximate/locality geometry never displays as exact
- OUTSIDE never becomes PR_LAND
- rejected candidate explanation remains queryable
- UNRESOLVED identity never becomes canonical automatically
- missing geometry remains explicit, not centroid-invented
- nulls/ties/duplicates/M:N joins do not silently corrupt counts

## 25. UFO Timeline bounded parity target

Observable reference features to adjudicate include:

- chronological timeline
- year navigation/filtering
- category filters
- News
- Documentaries
- Famous Cases
- Sightings
- Books & Documents
- Spotlight/highlight treatment
- Quotes
- People directory
- Websites/resources directory
- About
- Contribute
- broken-link reporting/contribution affordance
- share affordance
- per-entry deep links/content pages where observable

OVNIS-PR does not need identical editorial taxonomy. Every observable reference feature must receive one disposition:

`PRESENT | PARTIAL | ADD | EXCLUDE_WITH_REASON | NOT_APPLICABLE | UNRESOLVED`

Parity means 100% adjudication of the bounded observable surface, not blind cloning.

## 26. Known current UI risk to fix before productization

The existing GUI audit documents a Tailwind 4 migration defect where zero-value utilities such as `min-h-0` fail to compile under the current compatibility setup. With the Cases tab active, the long table can force the flex row/map to extreme height and make the MapLibre canvas appear as an invisible/sliver-like map. Fix and regression-test this before declaring Timeline/Map parity.

Also preserve the existing offline caveat: OSM basemap tiles are network-dependent even though corpus data remains local/offline-capable.

## 27. Certification boundary

`OVNIS-PR CORPUS CERTIFIED` may be issued only for a defined frozen scope with:

- frozen inputs
- explicit inclusion/exclusion
- full classification
- duplicate/edge adjudication
- arithmetic closure
- validated IDs
- bounded collisions
- passed temporal/spatial/source/provenance tests
- frozen manifests/hashes
- zero unresolved residue inside the certification claim

The corpus may be certified while individual object/explanation identities remain `UNRESOLVED`.

## 28. Execution order

C -> B -> A internally:

1. Corpus + authority foundation
2. Bounded UFO Timeline feature-parity adjudication
3. Public Timeline + Map productization
4. Research GIS extension
5. Cross-federation enrichment
6. Full positive/negative regression
7. Freeze manifestations + hashes
8. Certify only if residue inside scope is zero
