# Protected asset archive (HLB-448)

Archive bytes from the verified issue/association source and paginated issue
attachment metadata. Original source archives are immutable inputs. Start with
an existing environment credential and a new protected output outside Git:

```bash
python3 tools/linear_assets.py --issues /private/issues --associations /private/associations --output /private/new-assets
python3 tools/linear_assets.py --issues /private/issues --associations /private/associations --output /private/existing-assets --resume
```

Only exact HTTPS uploads.linear.app URLs receive the source authorization header.
This matches Linear's [file storage authentication documentation](https://linear.app/developers/file-storage-authentication).
Redirects, proxies, other hosts/schemes/ports, userinfo, fragments, control
characters and backslashes are denied. External-resource attachments (PRs, documents, build pages and plain URLs)
remain references; the official SDK schema defines Attachment.url as a link destination. Unsupported required image/file URLs become explicit blocked
entries and cause exit3; they are never silently considered preserved.

Metadata pages and the URL→source-owner→blob mapping are private0700/0600 files.
Each streamed blob has an SHA256 filename, checksum, size and durable local
`asset:sha256:<digest>` reference independent of the source URL's expiration.
URLs/signatures/raw metadata never enter console output. Files with identical
bytes share a single blob; distinct original references and owners are retained.
The checksum records observed bytes and detects later archive corruption; Linear
provides no mandatory independent expected checksum here, so it cannot prove the
provider sent an intended uncorrupted original.

Limits:64MiB per asset,512MiB aggregate metadata plus asset references' byte totals
(shared blobs counted conservatively per asset URL),10,000 metadata pages and
asset candidates,100,000 external references,16MiB per checkpoint/page,30s per
asset deadline/socket wait. One blocked read can extend past the remaining wall
clock budget by a socket wait. Transfers do not retry automatically; correct the
cause and explicitly resume the saved checkpoint. `--max-asset-bytes` and
`--max-total-bytes` allow bounded operator choices. A1GiB free disk reserve is a
conservative operation guard, not Plane runtime sizing.

Resume checks source manifests/profile, metadata provenance/scope/cursors/hashes,
all saved asset mappings, sizes/checksums and budgets before changing a completed
checkpoint. Rejected resumes preserve it byte-for-byte. A completed resume preserves its checkpoint byte-for-byte, reads
source scope once and makes no metadata/asset requests. Controlled failures and
cancellation remove in-flight files; committed assets/pages remain available.
CLI exit0 means all discovered assets archived,3 means blocked assets,2 means
input/transfer failure,130 means cancellation. No status means full migration.

If an uncontrolled process kill leaves `.part-<URL hash>`, inspect and explicitly
remove only the run-owned partial before resuming; the tool never overwrites it.
An uncommitted page causes an orphan-page error requiring operator recovery or a
fresh output, not automatic trust. Blob corruption fails closed; restore verified
bytes from a trusted backup or use a fresh output. Never overwrite a checksum
manifest to hide corruption. Preserve pre-existing outputs; concurrent writers
are denied with an exclusive lock.

Discovery recognizes Markdown/quoted HTML images, recognized rich-content image
fields and upload URLs embedded in currently exported strings/JSON arrays, plus
paginated issue attachment URLs. Unsupported image schemes are still recorded.
The selected source profiles do not yet export comments/history. Their assets
and unusual/custom content syntax remain explicit coverage work for HLB-454;
this command does not claim to have scanned unavailable source records. Owner
ledger/cutoff/native-import requirements from HLB-447 remain in force.

Local content-addressed storage is the protected migration archive. Storage
recovery/bucket provisioning belongs to R2; HLB-454 must upload/rewrite asset
references and verify authenticated rendering before native migration/cutover.
No Plane mutation, bucket deployment, source update, preview or service runs here.

```bash
TMPDIR=/var/tmp python3 tools/check_linear_assets.py --output /absolute/new-evidence
```

The runner retains a known-state pass, independently detects replaced bytes and
bypassed checksum validation, and repeats a restored pass. Its fixtures and
network responses are synthetic; no hosted test service or credential is needed.
