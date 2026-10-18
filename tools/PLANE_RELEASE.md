# Plane release candidates

`plane_release.py` prepares complete images without starting containers or
changing application data. HLB-433 owns this command; HLB-435 owns actual rollout.

Run with Python 3.9+ from a clean, pushed checkout. Provide the full commit SHA,
the exact remote branch ref, target `192.168.1.130` and a unique
`plane-rehearsal-<name>` namespace. `preflight` emits JSON and exits 2 on a gate
failure; errors contain codes, never raw tool stderr or credential material.

```bash
python3 tools/plane_release.py preflight \
  --repo /absolute/plane-checkout --revision <40-character-commit> \
  --ref refs/heads/agent/HLB-433-release-candidate \
  --target 192.168.1.130 --namespace plane-rehearsal-migration
```

The read-only SSH probe requires an existing trusted host key and SSH identity.
It checks free disk under the target Docker directory and MemAvailable. The
initial reservation is 10 GiB disk and 2 GiB available memory: a conservative
admission budget, **not measured proof** of Plane's steady-state/build needs.
HLB-434/435 must establish actual requirements before releasing a runtime.
There is no override to silently run on another host or shared namespace.

For `build`, also supply `--output /outside/checkout/candidate.json`,
`--python-base python@sha256:<64-hex-digest>` and
`--node-base node@sha256:<64-hex-digest>` and
`--nginx-base nginx@sha256:<64-hex-digest>`. Resolve compatible base digests through
the trusted image registry before running; mutable tags are rejected.

The builder snapshots **all tracked source** from the pinned revision, even from
a sparse checkout, and uses the full upstream API Dockerfile, not the legacy
wiki-file overlay. Backend modules/migrations, entrypoints, templates, copied
dependency files and manage.py are checked against the pinned Git blob inventory,
then hashed against an offline Docker image export. No `docker run/create`, service
host or compose deployment is used. Source revision/tree labels and immutable
image IDs are checked; API, worker, beat and migrator share the verified backend.
The frontend uses the same source snapshot and its complete upstream web build.

Candidate builds are mutually exclusive on one build host via a nonblocking
target-wide file lock held until completion. HLB-435 must add the target-side
release lock before any service mutation; this local builder lock is not a
distributed deployment lease. Failed builds may leave their uniquely tagged
candidate images for diagnosis but never emit a success manifest. Source
snapshots are removed in `finally`; output is outside the source checkout and
never overwritten. Other tasks' images/services are not removed.

Checks do not claim registry signature verification, live image startup,
database compatibility, authenticated readiness or a running deployment. Those
remain explicit later gates. Source archives must be reviewed: filenames catch
tracked credential files, not arbitrary secrets embedded in other source files.

Run the public command and image-contract tests without services:

```bash
python3 -m pytest -q tools/tests/test_plane_release.py -o addopts='' \
  --junitxml=/outside/checkout/preflight.junit.xml
```

Tests use real temporary Git remotes and external SSH/Docker contract fakes.
Synthetic saved-image layers check missing/changed/removed migrations and
symlink replacement. These tests do not prove a real image was built.

## Image packaging while deployment admission is pending

`preflight-package` performs the same source, exact-target, namespace and trusted
SSH checks, and records measured target capacity. It returns PACKAGING_ONLY and
a separate runtime_admission status. `package` then builds/verifies local images
with these checks. Insufficient runtime reservation never becomes a release PASS;
ordinary `preflight` and `build` retain their strict runtime capacity gate. These
commands do not start applications or change the target. HLB-435 must perform
fresh runtime admission, measured sizing, restore and readiness checks.

Build failures retain private 0600 backend/frontend logs in a new 0700 directory
next to the candidate manifest. Logs may include dependency URLs; keep them
outside Git. A retry uses a new output name. The manifest is published only after
both complete images and backend Git-blob comparisons pass. Build source temp
storage and the build daemon's disk usage must be monitored independently.

Packaging reserves temporary snapshot space from tracked Git blob sizes (three
copies, at least64MiB); this is separate from Docker layer storage and runtime
capacity. Frontend build stages use a2304MiB Node heap and one Turbo task at a
time. The manifest records these limits and the builder source checksum. These
are build controls, not measured application sizing or deployment admission.
