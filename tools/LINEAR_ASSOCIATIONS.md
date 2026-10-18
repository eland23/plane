# Linear association export

HLB-443 extends a verified HLB-442 issue archive. It writes a new protected
archive outside Git and leaves the input pages/manifest untouched.

```bash
# Existing credential is supplied through LINEAR_API_KEY, never a CLI argument.
python3 tools/linear_associations.py \
  --issues /absolute/private/issue-archive \
  --output /absolute/private/new-association-archive
# After correcting an auth/network/limit failure:
python3 tools/linear_associations.py \
  --issues /absolute/private/issue-archive \
  --output /absolute/private/existing-association-archive --resume
```

The current graph traverses team projects/cycles/labels/states/memberships, standalone team documents and
team-led initiatives;
issue-linked projects/cycles/labels and issue documents; project teams,
initiatives/documents/milestones/updates/members; initiative ancestors, documents/updates
and project UUID references; cycle documents and label groups/parents. Every
connection paginates with first50 and archived inclusion. Project members also
include disabled users. Existing document/update content and attribution remain
in raw pages; shared entities count once and every association edge is retained.
Foreign projects reached only through an initiative remain UUID references.

The source uses [Linear cursor pagination](https://linear.app/developers/pagination)
and queries checked against the [official SDK schema](https://github.com/linear/linear/blob/master/packages/sdk/src/schema.graphql).
Immutable UUID variables and static field selections prevent query injection.
No writes, hosted services, credential replay or URL/asset downloads occur.

Input and output must pass fail-closed Git-location/private-mode checks. Pages
and checkpoint are0600, output directory0700. Every page has a SHA256 and exact
connection/cursor provenance. Resume binds to the input manifest and exporter
fingerprint, replays saved pages/edges, and refuses corrupt or orphan files. The
checkpoint lock excludes concurrent output writers. Rejected validation leaves
existing manifest bytes unchanged. A power failure between page/checkpoint
commits may leave an orphan; retain it for explicit operator recovery.

The default limits are20,000 requests,512MiB archive bytes,16MiB per file/HTTP
response and1GiB disk headroom, plus the shared transport's bounded retries and
response deadlines. `--max-requests` and `--max-bytes` set explicit alternatives;
resume must use the original source and current exporter fingerprint.

`COMPLETE_FOR_ASSOCIATIONS` describes only these readable selected fields and
connections. It is **not** an atomic cutoff or complete migration backup.
Introspection inventories Issue field names and observed issue-field presence;
custom usage that is unexposed or unqueried is explicitly unknown and requires
HLB-447 disposition. Unselected fields, changes/deletions, nested document
history/comments and unrelated workspace objects are not silently claimed.
HLB-447 owns complete coverage/final deltas; HLB-448 owns asset bytes.

Run the committed synthetic proof without credentials or hosted dependencies:

```bash
TMPDIR=/var/tmp python3 tools/check_linear_associations.py --output /absolute/new-evidence
```
