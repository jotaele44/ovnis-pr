# Source sweep ledger and duplicate gate

Recurring searches for new Puerto Rico UAP cases waste effort when they re-cover sources that are already
worked, and they put the same event in the log twice when a second site republishes it. This ledger records
how far each source has been swept. The duplicate gate checks a candidate against every case already known
before it is staged.

Both are bookkeeping for curators. Neither writes to the master ledger, promotes a case or merges two cases.
Promotion stays a reviewed step under [`CASE_PROMOTION_STANDARD.md`](CASE_PROMOTION_STANDARD.md).

## Files

All three are CSV files under `data/reference/` and are maintained through `scripts/sweep_ledger.py`.

| Path | Holds |
|---|---|
| `data/reference/source_sweep_ledger.csv` | One row per source: how it is swept, what the log already holds from it, and how far a sweep has been verified. |
| `data/reference/sweep_query_log.csv` | One row per search run, so the same query is not run twice on the same source. |
| `data/reference/known_case_index.csv` | Lookup keys (date, place, normalized source URLs) for every case in the working Case Log workbook. The gate reads it. |

The master ledger (`data/master/master_cases.jsonl`) is read by `check` as well, and never written.

**The index is not the master ledger.** It covers the working Case Log workbook, which is a research
collection of candidate cases and holds more cases than the master ledger (793 against 470 at the time of
writing). Having a row in the index does not mean a case was promoted. Promotion of workbook
cases into the master ledger goes through the standard linked above.

## Source states

Each ledger row has a `state` that says what a sweep of that source means.

| `state` | Meaning | What to do |
|---|---|---|
| `forward` | A live collection that keeps growing. | Sweep the bounded interval to its verified prior frontier; record coverage gaps. |
| `closed` | A static collection that was swept in full. | Do not sweep again. Re-open only if the source changes. |
| `citation_only` | Specific pages are cited, but the source was never swept as a collection. | Nothing to sweep. Promote to `forward` or `closed` only after a real collection sweep. |
| `not_started` | A collection-level sweep is wanted and has not been done. | Plan a sweep, then record it. |
| empty | Unclassified. | `status` lists these so they get a decision. |

`kind` is `live` or `static`. `access` is `open`, `blocked_automated`, `manual_only` or `unknown`.
`blocked_automated` means the site refuses scripted fetches (NUFORC, UFO-Hunters.com and
ufosighting.report at the time of writing). Load those pages in a browser or use an export.

### How the first classification was made

The initial `state`, `kind` and `access` values are rule-based first guesses, not verified findings:

- a report database, a named live site, or social media or video is `live`; everything else is `static`;
- a live source is `forward` when it has four or more logged references or is a report database, and
  `citation_only` otherwise;
- a static source is `closed` when it has four or more logged references, and `citation_only` otherwise;
- social media rows are always `citation_only`;
- a few sources are set by hand: UFO Sightings Daily, AARO, UFO Stalker, the War Department UAP release and
  the CIA copy released through it are `forward`.

At the time of writing that gives 14 `forward`, 18 `closed` and 70 `citation_only` sources. Every
`verified_through` and `last_swept` value is empty, because no sweep has been recorded through this tool yet.
A curator who knows a source was in fact swept in full should correct its state with `record`.

Earlier sweeps were not query-logged, so `sweep_query_log.csv` starts nearly empty. A missing log row does
not mean a search was never run.

## Computed and manual columns

`refresh` recomputes `cases_logged`, `refs_logged`, `oldest_logged_event`, `newest_logged_event` and
`highest_item_id` from the Case Log workbook. It never touches `state`, `kind`, `access`, `verified_through`,
`last_swept`, `next_action` or `notes`.

Event dates are informational only. A source can publish a post today about an event from 1998, so the
newest event date logged is not a high-water mark for what was swept. The point a sweep reached is the receipt-backed `verified_through` value. A highest logged item ID is a discovery hint, not evidence of contiguous coverage.

## Workflow

1. `python3 scripts/sweep_ledger.py status` lists forward sources that were never verified or are older than
   `--stale-days` (default 90), unclassified and not-started sources, and sources blocked to automation.
2. Before running a search, `python3 scripts/sweep_ledger.py query "<text>" --source "<site or engine>"`
   with matching language and scope reports whether it was already run within `--within-days` (default 90). It exits 1 if so.
   Add `--log` with `--results` and `--new` to record a run.
3. Sweep newest first. Run each item through `check` before staging it:

   ```
   python3 scripts/sweep_ledger.py check --url <URL> --date "October 5, 2026" --municipality Salinas
   ```

   `--jsonl <file>` checks a batch, one candidate object per line. `--fail-on-match` returns 1 for any verdict other than `NO_KNOWN_MATCH`; unavailable comparison inputs return 2.
4. Stop only when the bounded interval has been reconciled. Known items alone do not establish coverage.
5. `python3 scripts/sweep_ledger.py record --source "<name>" --verified-through "<position>" --receipt <receipt.json> --note "<what was done>"`
   records the point reached and the date after validating the receipt and evidence bytes. Use `--add --category ...` for a new source.
6. After cases are added to the Case Log workbook, `python3 scripts/sweep_ledger.py refresh --xlsx <workbook>`
   rebuilds the index and the computed columns. The output is deterministic.

## What `check` reports

| Verdict | Meaning |
|---|---|
| `EXACT_REPORT` | A source-native report identifier matches without detected metadata conflict; review still required. |
| `IDENTITY_CONFLICT` | A matching native report has contradictory date or municipality metadata. |
| `SHARED_DOCUMENT` | A normalized document URL overlaps; event identity is not established. |
| `POSSIBLE_DUPLICATE` | No shared URL, but the recorded dates agree and the place agrees. |
| `NO_KNOWN_MATCH` | No match found with minimum candidate metadata; not proof of novelty. |
| `INSUFFICIENT_IDENTITY` | No match found and minimum metadata is absent. |
| `COMPARISON_UNAVAILABLE` | Required comparison inputs are missing or invalid. |

URLs are compared by a normalized key, so these count as one source: a NUFORC `S79425.html` page and the
`?id=79425` page, a ufosighting.report link with a different slug, a UFO-Hunters link in a different case,
a Wayback Machine copy and its original, and a link with tracking parameters. A citation that is not a URL
(for example a publication and month) has no key and never matches on source.

For `POSSIBLE_DUPLICATE` the date and the place must agree together:

- **Date.** The same rules as `scripts/dedupe_candidates.py`: dates agree at the coarser precision, so `1972`
  agrees with `1972-10-13`. Two full dates one day apart also count (`ADJACENT_DAY`), because reports of the
  same evening often differ by a date. A candidate with no date can never be a possible duplicate.
- **Place.** A shared municipality (several may be listed, as in "Ponce / Guayanilla"), or, when either side
  has none, near-identical location text (ratio of 0.85 or more). Two different municipalities never match.
  A value that does not name a place, such as "Island-wide", anchors nothing.

A possible duplicate is a prompt for review, not a decision. Similarity never decides identity
([`RESEARCH_LEDGERS.md`](RESEARCH_LEDGERS.md)). Near-duplicates that differ in real ways stay as separate
cases, with the difference noted.

## Relationship to the other tools

- `scripts/import_candidates.py` and `scripts/dedupe_candidates.py` stage and compare candidates against the
  master ledger. `sweep_ledger.py check` reuses the date and location rules of the latter and adds the
  working-workbook index, source-URL keys, persistent intake ledgers and earlier candidates in the current batch.
- `data/reference/source_registry.csv` declares sources and their cadence for the federation export.
  The sweep ledger does not replace it and does not feed `source_monitors.jsonl`. It is a curator's record
  of sweep coverage, not a fetch-run receipt, so a `last_swept` value records a receipt-backed curator assertion, not an independently authenticated fetch run. Only `data/source_run_state.json` can mark a source as having run successfully, and nothing writes
  to it yet.

## Tests

`tests/test_sweep_ledger.py` covers URL normalization, date and place agreement, the current verdicts, `record`,
`status`, `query` and `refresh`, and checks that the committed ledger and index use the declared columns and
vocabulary. The `refresh` test needs `openpyxl` and is skipped without it.

## Receipt and writer integrity

Frontier updates require a local JSON receipt with source, execution_id, interval_start,
previous_frontier, verified_through, sweep_date, status (success), reconciliation (complete),
configuration_path, configuration_sha256 and a nonempty evidence array of path/sha256 objects.
Paths must resolve inside the receipt directory. The configuration and evidence bytes are hashed.
Existing frontiers support increasing numeric IDs or ISO dates; other representations cannot be advanced
without additional progression rules. Identical validated receipts are idempotent. Receipt assertions do
not independently prove source completeness or issuer authorization.

CLI mutations use exclusive sibling lock files and atomic CSV replacement. A lock left by an interrupted
worker must be reconciled before retrying; never delete an active writer's lock. Refresh is not an atomic
multi-file transaction. Unattended recovery and publication privacy qualification remain separate gates.
