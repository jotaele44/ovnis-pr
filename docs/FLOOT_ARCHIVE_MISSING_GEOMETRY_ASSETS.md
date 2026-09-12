# OVNIS Floot archive missing-geometry asset binding

Status: OPEN / BOUNDED

The archived `Ovnis PR.zip` does not contain the four geometry/topology artifacts referenced by its own W8 manifests. Source absence from the ZIP is not evidence that the artifacts never existed elsewhere.

## Missing members

| Artifact | Expected SHA-256 | Role |
| --- | --- | --- |
| `municipios-2015-derived-wgs84.geojson` | `d0924e22cbffb4dd44b7bb038af38e75bdd9fca633f6089b3c99c4ffd20d73b5` | Historical 2015 derived WGS84 municipality geometry |
| `municipios-2023-derived-wgs84.geojson` | `25687f067d469609392e9761aa183cfe81d791026a5c10c4ec5b933b1e492b02` | Current 2023 derived WGS84 municipality geometry |
| `municipios-2023-visual-10m.geojson` | `b50b9c227dfd5562b7a3bd85309d5802d80d6ad16546f27e452eba5cfa49e691` | NONCANONICAL_VISUALIZATION_ONLY simplified geometry |
| `boundary-topology-comparison-v2.json` | `c89b584eca52e7aa38fae2151b946f03c94ccb430f244256bd7a6be1e1c172ed` | 2015↔2023 topology comparison receipt |

## Source manifestation already preserved by donor metadata

The donor records a 2023 Planning Board / GeoServer source ZIP manifestation SHA-256 of `4849c09b86ffd58e4e9e5beeda75510469d8f2b9e9c0be01c991bd586c55907c` and preserves a six-member PATH + UNCOMPRESSED_SIZE + SHA256 manifest. It classifies distinct outer ZIP hashes with identical member payloads as `PURE_RECOMPRESSION` rather than distinct geometry payloads.

This metadata is evidence for expected identities only. It does not substitute for the missing artifact bytes.

## Recovery gate

A recovered candidate may be admitted only if:

1. filename/path role is independently established;
2. byte SHA-256 equals the expected value above;
3. GeoJSON feature denominator and geometry/schema invariants match the frozen W8 receipts where applicable;
4. source/derived/visualization roles remain separate;
5. no regenerated geometry is claimed byte-identical to the missing historical artifact unless the expected hash matches exactly.

If an exact-hash artifact cannot be recovered, classify the historical manifestation `UNRECOVERED`; a newly regenerated equivalent may be stored as a new manifestation with a new hash and explicit derivation provenance, never as the missing original.
