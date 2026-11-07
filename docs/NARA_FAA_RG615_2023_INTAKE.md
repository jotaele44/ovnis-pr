# NARA RG615 FAA UAP intake — 5 source documents (2023)

State: PROVISIONAL / AUDIT_ONLY / NONCANONICAL. No master ledger edited.

The five records are *report identities*, not five certified physically distinct phenomena. Four external incidents involving departing PR flights; one San Juan report is already in the master: PRUFON-0449 / PRUAP-0449. Its entry is an **evidence update**, not a new case.

Intake records: `nara_faa_rg615_2023.jsonl` (5 rows, 4 candidate / 1 update_existing). The existing `SRC-0005` FAA source family is reused; no new registry source category or numeric master IDs created. Separate geographic relationship `geo_scope` from actual event location. Out-of-PR coordinates intentionally never enter the PR-bounded canonical `latitude`/`longitude` columns.

## Critical gates

- Files are text extracts previously retrieved from NARA PDFs, source-document SHA256 values recorded in intake. This commit does not bundle original PDF binaries. Reacquire and validate PDF sizes/hashes and perform page-level visual verification for promotion.
- For FedEx 52 and JetBlue 1348: the header coordinates (38.35,-67) and the narrative (24°29'N,72°50'W) contradict. Preserve both; canonical GIS geometry is NULL pending adjudication.
- Both Atlantic reports share a reported coordinate and occur within one minute of each other, but belong to distinct flight reports; keep full candidate linkage, do not merge automatically.
- NARA / FAA evidence establishes that the flightcrew reports were logged, *not* an extraordinary origin of the observations.
- Report timestamp labels for Atlantic PDFs ('-00 Local', '2300E' and '2301E') require timezone adjudication; avoid assigning UTC/Puerto Rico time without proof.
- Reconcile candidate cases against master and every active ledger and check each `naId`/FAA identifier to exclude duplicate imports. GitHub code search alone is not an exhaustive absence proof.
- Before promotion, validate schema, JSONL parse, row counts=5 (4+1), IDs unique=5, source family='FAA', all NARA URLs nonblank, null GIS coords=5, existing case ID PRUAP-0449 unchanged, master unchanged. Public site may require a separate federated view for PR-origin reports outside Puerto Rico.

## Original source links

- FFT101: https://catalog.archives.gov/id/499915797 ; PDF https://catalog.archives.gov/medialz/electronic-records/rg-615/493468575/237UAP00498.pdf ; SHA-256 029de8d3664b276e69e2cb7a081a83b83492b14efe7584a30608d30a5bdf1da2
- NKS1900: https://catalog.archives.gov/id/499915817 ; PDF https://catalog.archives.gov/medialz/electronic-records/rg-615/493468575/237UAP00519.pdf ; SHA-256 bf7da9f708bc2b292ca0253cb9da26b572ed9b76f09cdc784bf2058451c907e7
- FDX52: https://catalog.archives.gov/id/499915833 ; PDF https://catalog.archives.gov/medialz/electronic-records/rg-615/493468575/237UAP00535.pdf ; SHA-256 8534aa9997e97d98c6739139e19e6a9d278ec91eea7a36721298fbda8a953aea
- JBU1348: https://catalog.archives.gov/id/499915834 ; PDF https://catalog.archives.gov/medialz/electronic-records/rg-615/493468575/237UAP00536.pdf ; SHA-256 35827c483212c8f1121f863230ea25eb35567669b0725c14e065c2883e4f471f
- FFT4139: https://catalog.archives.gov/id/499915869 ; PDF https://catalog.archives.gov/medialz/electronic-records/rg-615/493468575/237UAP00573.pdf ; SHA-256 ec93312335befbcf99f016a6075d975b902717c0a9c3f670ec1dbcc772a30168

## Review and promotion sequence

Freeze PDF bytes → verify SHA256 and layout → complete full-ledger dedupe → adjudicate UTC/local times, header/narrative coordinates, and aircraft positions → link all reports to the NARA source manifestation → update existing PRUAP-0449 without duplicate case → assess promotion of the four geographically external reports in a separate PR-connected collection that does not corrupt Puerto Rico-only geospatial exports.

## Reproducibility

Use this repository's `python3 scripts/validate_case_ledgers.py` and unit tests. The staged JSONL has the current permissive case schema fields plus noncanonical evidence metadata. DO NOT infer that a validator PASS certifies event identity or source geometry.
