# Snapshot deltas and coverage (HLB-447)

This read-only CLI compares two validated issue/association archives and records
source coverage against a separately captured schema inventory. It does not
import, delete, freeze Linear, or authorize cutover. Use protected directories
outside every Git ancestor; outputs are new 0700 directories and 0600 files.
Credentials belong only in the existing environment, never command arguments.

```bash
python3 tools/linear_coverage.py capture-schema --team TEAM_UUID --output /private/new-schema
python3 tools/linear_coverage.py compare \
  --before-issues /private/old-issues --before-associations /private/old-associations \
  --after-issues /private/new-issues --after-associations /private/new-associations \
  --schema /private/new-schema --output /private/new-report \
  --cutoff 2026-10-18T00:00:00Z
```

Capture-schema returns 0 for all exposed types, 3 for a completed inventory with
unavailable/blocked types, 2 for input/provider failure. Compare returns 1 for
named changes, 3 for equal source records with outstanding readiness gates, and
2 for invalid input. Cancellation returns 130 at the CLI boundary. These nonzero
comparison verdicts are intentional. Standard output contains counts only;
protected reports include source IDs, field paths and value hashes, not values.
The protected input pages still contain original private source payloads.

## Final delta procedure

1. Keep the baseline issue and association archives immutable. Capture a fresh
   issue export, then a fresh association export from that issue archive using
   the existing HLB-442/443 commands. Completed `--resume` replays local pages;
   it is not a new observation. Record schema access with capture-schema.
2. Compare the baseline and new archives. Investigate every named entity, field,
   edge, Issue schema change and intra-snapshot conflict. A missing record is an
   unconfirmed tombstone candidate: deletion, permission loss and scope changes
   remain distinguishable only with further evidence. No inaccessible record is
   silently treated as deleted or fully preserved.
3. After an authorized source freeze, repeat fresh exports and comparison. The
   operator must independently establish the freeze and cutoff; equal REST/
   GraphQL read windows cannot prove an atomic or historical as-of snapshot.
   Post-cutoff event timestamps remain explicit exceptions. Observation identity
   binds original capture starts, query profiles, scope and ordered page hashes;
   both issue and association captures must differ, in chronological order.
   This is local archive provenance, not cryptographic provider attestation.
4. Resolve feature-owner dispositions for every workflow-critical field and
   exception. Only later destination verification (HLB-455) can establish native
   preservation and readiness. This command always retains the native-import,
   verified-cutoff and owner-disposition gates.

## Ledger semantics and ownership

Every configured migration category gets rows for all enumerated schema fields
plus observed fields, or an explicit wildcard if the type is inaccessible.
Available fields with preserved payloads are `archive`; no field is automatically
`native`. Unread fields remain `blocked` with unknown usage; absent types are
`unavailable`; fields removed from the current schema are `unsupported`.
Exact credential field names are explicitly excluded, never requested by the
export profiles, and do not ask an owner to migrate credentials. This is not a
promise that every provider secret field name is known.

Presence and usage differ: null, empty text/list/object and empty connections
are not populated. False and zero are meaningful values. Connection pageInfo
is transport metadata, not domain usage. Nested objects/relations are marked
partial; preserving an object ID does not prove all its fields were exported.
Custom-property and work-item-type usage remain unknown until explicitly
queried and resolved, even if no candidate field appears in this inventory.
The prior schema comparison currently covers Issue only; other historical type
schemas were not retained by the baseline exporter and are explicitly unverified.

HLB-448 owns authorized attachment/image bytes; HLB-453 owns planning graph
mapping; HLB-454 owns content/history import; HLB-455 owns full destination
reconciliation. Comments, reactions, history, subscriptions, views, templates,
SLA and integration categories can be enumerated in this ledger without their
records having been exported. A source schema is a capability inventory, not
proof that a credential can read every record of that type. Further export
profiles/owner decisions must close those gaps before cutover. No child ownership
waives the parent migration requirements.

## Verification

```bash
TMPDIR=/var/tmp python3 tools/check_linear_coverage.py --output /absolute/new-evidence
python3 -m pytest tools/tests/test_linear_export.py tools/tests/test_linear_associations.py tools/tests/test_linear_coverage.py -q --basetemp=/var/tmp/new-test-fixtures
```

The saved runner requires clean passes before and after deliberately suppressing
modified fields and removed edges in temporary source copies. Unchanged tests
must fail at their literal business assertions. Fixtures are synthetic, external
requests controlled, and every temporary root is removed. CI uses no credentials.
No application services or preview servers are involved.
