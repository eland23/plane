# Verification evidence: HLB-448 protected asset archive

Status: **PASS for the HLB-448 discovered asset archive; parent HLB-431 INCOMPLETE**.
Author: Codex. Separate Standards and Spec/security source reviews: PASS.
Tracking: [HLB-448](https://linear.app/fashionfindrs/issue/HLB-448), parent
[HLB-431](https://linear.app/fashionfindrs/issue/HLB-431), [PR9](https://github.com/eland23/plane/pull/9).
Policy: FashionFindrs `docs/testing/POLICY.md` and `REPORT-TEMPLATE.md`.

## Scope and coverage

Public seam: `asset_integrity_contract`. All tests below are saved in
`tools/tests/test_linear_assets.py`; all rows belong to HLB-448. No coverage
claim extends beyond the corresponding source archive behaviors.

| Behavior ID | Owned AC | Saved test | Independent assertion | Layer | Result/evidence |
|---|---|---|---|---|---|
| MIG-03 binary/image | AC3 | asset_bytes_hash_durable_reference_and_pr_link_are_preserved | Literal19 binary bytes/SHA256, two URL mappings/one shared blob, stable local references, external-resource links remain links, private modes and no source mutation | pytest/API contract/filesystem | PASS / pass-known-state.xml |
| MIG-03 completed resume | AC3,V2 | completed_asset_resume_verifies_bytes_without_redownload | One scope request, zero metadata/blob requests; byte-identical checkpoint and capture time | pytest/API contract | PASS / pass-known-state.xml |
| MIG-03 URL/credential boundary | AC3 | disallowed_url_never_receives_credentials; redirect_is_denied_without_forwarding_authorization | Eight denied scheme/host/port/userinfo/IP/fragment/control cases never call opener;302 cannot forward auth | pytest/HTTP contract | PASS simulated / pass-known-state.xml |
| MIG-03 required image classification | AC3 | external_image_is_explicitly_blocked_without_fetch; rich_image_field_and_html_image; non_http_image_references_remain_explicitly_blocked | Markdown/HTML/rich fields on unsupported hosts/schemes become BLOCKED; no denied fetch;3 protocol-relative/file/ftp combinations remain visible | pytest/API contract | PASS / pass-known-state.xml |
| MIG-03 oversize/truncated stream | AC3,V2 | oversize_stream_cleanup_then_resume_with_correct_limits; truncated_stream_never_commits_blob | Oversize fails explicitly, no partial file; corrected resume succeeds; length mismatch commits no blob | pytest/stream/filesystem | PASS / pass-known-state.xml |
| MIG-03 stored corruption | AC3,V2 | corrupt_committed_blob_rejected_without_mutating_checkpoint | Corrupted literal blob blocks resume with byte-identical checkpoint; verified byte restoration allows resume | pytest/filesystem | PASS / pass-known-state.xml |
| MIG-03 scope/pagination | AC3 | foreign_attachment_is_denied_before_private_page_commit; attachment_pagination_retains_second_page_and_denies_cursor_loop | Foreign-team raw page never persisted; seven pages/six issue scopes and second-page PR retained; loop fails after one committed page | pytest/API contract | PASS / pass-known-state.xml |
| MIG-03 cancellation/recovery | V2 | cancel_removes_partial_stream_and_resume_keeps_metadata; metadata_failure_preserves_checkpoint_and_corrected_resume | Interrupted stream cleaned; auth loss/request-limit checkpoint retained; corrected resume avoids committed metadata requests | pytest/API contract/filesystem | PASS simulated / pass-known-state.xml |
| MIG-03 rejected resume | V2 | rejected_resume_plan; rejected_resume_structure_and_budget | Tampered URL, duplicate key, owner mismatch and lower budget reject before any checkpoint change | pytest/filesystem | PASS / pass-known-state.xml |
| MIG-03 isolation | V2 | lock_and_no_overwrite_preserve_existing_source_and_assets | Concurrent writer and overwrite denied; original inputs/output checkpoint byte-identical | pytest/filesystem | PASS / pass-known-state.xml |
| MIG-03 external-resource semantics | AC3 | external_attachment_resources_remain_links_without_fetch | Three literal build/document/VM URLs remain unfetched external-resource links, matching the provider Attachment model | pytest/API contract | PASS / pass-known-state.xml |
| MIG-03 failure detection | V2 | unchanged literal-byte/hash and corrupt-blob assertions | Replacing transferred bytes and bypassing checksum gate fail at intended business assertions, restoration passes | pytest/fault controls | PASS / failure-*.xml and restore-and-repeat.xml |
| MIG-03 live source | V3 | protected source run + independent verify_assets.py | Every selected issue's attachment pages terminal, source binding/page hashes and discovered blob integrity read back | read-only Linear API/offline | PASS / live-readback.json and live-resume.json |
| Native bucket/upload/rewritten rendering | parent AC3/6 | R2 and HLB-454 | Source archive is not destination storage recovery or native content proof | API/UI | NOT RUN here; separate ownership |
| UI/Jest/browser/TesterArmy | V1 | N/A | Python CLI only; no UI/TypeScript/hosted service | UI/Jest | N/A |

Inventory:15 behavior rows,13 PASS,1 separately owned
NOT RUN,1 N/A;0 approved deferrals. The six issue identifiers/UUIDs in tests
are synthetic source fixtures, never resolved against live Linear. Full native
fixture M and destination authorization/persistence belong to import children.

## Provenance and reproduction

Application/test revision: `1d6579e8f1371b1ceab707acbd2793a5aa6fb5c8`, clean and
pushed before live execution. Matrix and combined suites used the same exact
source/test bytes; the report/verifier/artifacts are a later evidence commit.
Python3.9.2, pytest8.4.2. Attachment query validates with zero errors against the
official Linear SDK schema retained during this migration; this proves protocol
shape, not provider record visibility. All controlled HTTP/GraphQL objects are
external boundary fakes; tests do not mock internal exporter collaborators.

```bash
TMPDIR=/var/tmp python3 tools/check_linear_assets.py --output /absolute/new-evidence
python3 -m pytest tools/tests/test_linear_export.py tools/tests/test_linear_associations.py tools/tests/test_linear_coverage.py tools/tests/test_linear_assets.py -q --basetemp=/var/tmp/new-fixtures
python3 tools/linear_assets.py --issues /private/issues --associations /private/associations --output /private/new-assets
python3 tools/linear_assets.py --issues /private/issues --associations /private/associations --output /private/existing-assets --resume
```

Only an existing LINEAR_API_KEY environment credential is used. Raw source
records, signed URLs and blob contents are private; no credentials or actual
source URLs/UUIDs are committed. Synthetic native logs/JUnit are retained in Git;
CI uploads its credential-free matrix for30days. Trailing horizontal whitespace
normalization only is disclosed with original/committed hashes in
`artifact-normalization.json`; assertions and JUnit counts are unchanged.
Source/test file hashes are recorded in `source-provenance.json`.
Deployment/image identity/VM URL: N/A, read-only CLI with zero destination writes.
No service, preview or container started, and existing .129/.130 services/data
remain untouched. Exact-head CI is a separate merge gate.

## Three-check receipts

| Check | Actual | Exit | Artifact |
|---|---|---|---|
| Pass from known state |32 cases,10.830s |0 | artifacts/pass-known-state.xml and .log |
| Detect replaced bytes |1 intended literal-hash assertion failure,1.169s |1 | artifacts/failure-replaced-bytes.xml and .log |
| Detect checksum bypass |1 intended missing-rejection failure,1.409s |1 | artifacts/failure-checksum-bypass.xml and .log |
| Restore and repeat |32 cases,9.643s |0 | artifacts/restore-and-repeat.xml and .log |
| Combined source exporter suite |101 cases,26.793s |0 | artifacts/combined-regressions.xml |

Faults modify only temporary production-source copies, never saved assertions.
The byte control replaces each streamed chunk with equal-length different bytes;
the literal golden checksum assertion detects this independently. The second
control bypasses committed-blob verification and must fail the unchanged
corruption rejection assertion. Both negative JUnit outputs have one failure,
zero errors. Normal source then passes with fresh fixtures. All four matrix
roots were removed; `receipts.json` records absence after passing/failing runs. Additional task-owned development/combined-suite fixtures were removed after evidence collection; `manual-fixture-cleanup.json` records all16 roots absent. Protected real source archives remain intentionally retained.
Earlier public red regressions independently caught invisible non-HTTP images
and checkpoint mutation on rejected resume; both now pass. Initial missing-file
setup during TDD is not counted as the required failure-detection proof.

## Error handling and recovery

Controlled dependency injections cover403-like GraphQL denial, redirects,
foreign issue/team, pagination loops, oversized/short streams and interruption.
Denied provider bodies/token values never reach saved failure codes. Source
scope is checked before attachment pages are saved. Metadata/page limits fail
explicitly with a committed checkpoint; valid resume replays and verifies local
pages, checks all canonical URL/owner/blob mappings and combined budgets before
writable checkpoint state. Concurrent writer/overwrite are denied. Corrupt saved
bytes require trusted restoration or a fresh output; no silent checksum rewrite.
Controlled stream errors/cancel clean in-flight files. Hard-kill partial/orphan
recovery requires explicit operator inspection, as documented in
`tools/LINEAR_ASSETS.md`. The query profile also binds implementation bytes, preventing incompatible discovery rules from reusing an old archive. No unbounded automatic retry; manual corrected resume
is proven. CLI statuses:0 all discovered assets archived,3 blocked assets,2
input/transfer failure,130 cancellation.

## Security, limits and coverage boundaries

Threat model: `docs/security/threat-models/HLB-431-linear-export/THREAT-MODEL.md`.
ASVS V5 input validation, V7 safe errors, V8 private storage and pipeline reviewed.
Only exact HTTPS uploads.linear.app receives the source authorization header;
proxies/redirects are disabled and status/final URL checked. The provider owns
this fixed trusted hostname; no user-controlled DNS target is accepted. See
[Linear storage authentication](https://linear.app/developers/file-storage-authentication).
No arbitrary fetch, source mutation, content/LLM execution or destination write.

Limits:64MiB/asset,512MiB combined metadata plus URL-mapped asset bytes,10,000
pages/candidates,100,000 external links and16MiB private checkpoint/page. Shared
blobs count per URL conservatively.30s stream deadline and socket timeout bound
transfers; one blocked read may extend past the remaining deadline by one socket
wait. The1GiB free disk guard is a conservative reserve, not measured Plane sizing.
A SHA256 proves retained observed-byte integrity; no mandatory independent source
checksum is exposed here, so upstream semantic corruption is not certified away.

Discovery covers selected current issue/project/document/update payloads and
paginated issue attachment metadata. Standard Markdown/quoted HTML/rich image
locations on unsupported schemes/hosts remain explicit blocked entries. Unread
comments/history and unusual/custom content syntax remain coverage gaps under
later HLB-454 and the HLB-447 ledger. This is not a full migration backup. Durable
local content-addressed references still require bucket upload/rewrite, recovery
and authenticated destination rendering under R2/HLB-454/455 before cutover.
Owner dispositions, reconciled deltas and verified cutoff remain parent gates.

Execution metrics are in native artifacts; no flaky retries or model/provider
content generation. Model input/cached/output tokens and billed cost unavailable;
no cost-saving/cache-hit claim. Completed resume verifies local data without redownloading or changing checkpoint/capture metadata.

## Live evidence and cleanup verdict

The final clean pushed source1d6579e enumerated all801 selected issue scopes,
801 terminal attachment pages and555 external-resource attachment records.
Source window:2026-10-18 21:41:04.495–21:44:14.860 UTC. It archived25 upload
assets/25 unique blobs totaling57,269,718 bytes, with0 blocked discovered assets.
5,986 reference rows (not necessarily unique URLs) remain links. External
Attachment.url values represent linked resources per the provider model; they
are not automatically treated as file-download requests.

Independent `verify_assets.py` recomputed source manifest bindings, source and
attachment page hashes, terminal issue scope/pagination, every blob SHA256/size,
private directory/file modes, source-reference presence and external attachment
link mappings. No partial files remain. The sanitized results are in
`artifacts/live-readback.json`; `live-summary.json` records aggregate facts and
the private manifest hash only, never source URLs/IDs or file content.

Completed service resume made exactly one source scope request, zero metadata
requests and zero asset fetches; both inputs and the entire asset checkpoint
remained byte-identical. The public CLI completed resume with exit0 and the same
checkpoint. `artifacts/live-resume.json` retains the receipt. This is verified
local readback, not an independent new source observation. The independent
checker also passed a six-issue/two-asset/one-shared-blob synthetic fixture.

Canonical private asset archive:
`/var/lib/plane-migration/HLB-448-assets-final-20261018`. An earlier preliminary
capture remains private for recovery and is not the canonical source for import.
Use the final archive named here. Source inputs are the HLB-447 issue/association
archives; real records and bytes remain outside Git. No capture is atomic or
establishes a source freeze/cutoff. Comments/history and their assets remain
later content-export/import coverage, not silently claimed preserved here.

```bash
python3 docs/verification/HLB-448/verify_assets.py --archive /private/final-assets \
  --issues /private/issues --associations /private/associations
```

Separate Standards and Spec/security reviews PASS for source; final evidence
review/CI on the complete PR head are recorded in PR/Linear comments. Matrix
fixtures and the additional16 task-owned development/combined fixture roots
are absent after evidence collection. Protected real archives are intentionally
retained; no cleanup failure, unresolved source finding or flaky test retry.
Owner decisions, verified cutoff, destination upload/rewriting/recovery and
native user journeys remain parent gates. No Plane import, deployment or cutover
is authorized by this report.
