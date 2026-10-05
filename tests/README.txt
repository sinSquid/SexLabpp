Core regression tests

Requires a C++20 compiler with std::format and Python 3.12+.
Create an isolated Python environment, install tests/requirements.txt, then run:
    python tests/run.py
Set CXX to select the compiler (default clang++).
Windows source contracts:
    pwsh -File tests/review_invariants.ps1

The suite compiles standalone utilities and extracts production functions for
statistics, path finding, recognition state, CSV and model prediction into small
engine stand-ins. It does not load a Skyrim DLL, validate hooks, compile Papyrus,
or prove VM scheduling/engine object lifetime behavior. The statistics fixture
models the v1 MSVC x64 variant layout explicitly; a real cosave is still required
for integration acceptance.

Source callback checks remain separate from behavioral tests. The GitHub workflow
runs behavior tests on Linux and atomic replacement/source contracts on Windows.
No generated binaries or Python environments are stored in the repository.

Second-review coverage: strip delete/reset and atomic reload (production functions
with in-memory YAML/engine stand-ins); production ML session handoff outside the
frame mutex; archive filename gaps/concurrent publishers and failure recovery;
edit-version save receipts; encounter saturation/v2 roundtrip; bounded dense
cyclic graph search. Real yaml-cpp parsing and Windows/game execution are separate.

Behavior limits: cyclic longest-path searches stop after 100000 edge visits
and return the best discovered simple path, with a warning. Failed ML batches
remain in memory, retry on the next training-state change and once at orderly
queue shutdown. Persistent disk failure or process termination can still lose
unsaved batches; Flush waits for attempted writes and is not a success receipt.

Third-review coverage: actual Decode.h allocation-before-validation guards,
truncated integers, bounded string/count reads, and signed fixed-point decoding.
ML status snapshots are trivially copyable and do not include recorded samples.
SLR caps: strings 1 MiB, package scenes 100000, tags/annotations per list 4096.
These reject oversized packages; full game asset loading remains an integration check.

Fourth-review coverage: raw and typed SLR reads share one cached byte budget;
readers initialized at a nonzero offset, raw overruns, 4096-node chains, parallel
graph edges and unreachable cycles. Reader construction measures the remaining
file length once; all package constructors now consume Decode::Reader.

Full file review: full_review_regressions.py exercises actual tracking v1 methods
with byte-stream and engine stand-ins, every truncation, count/delimiter corruption,
concurrent callback snapshots, 1000 randomized geometry cases, default coordinates,
legacy voice selection and copy-free lookup, and min/max edge cases. Failed-start
Papyrus cleanup and ImGui clip restoration are source contracts, not runtime tests.

Second full file review: full_second_review.py covers PCA seed degeneracy and tiny
motions, antiparallel rotation limits, projected angles, 200 rotated object-bound
and SAT cases, containment displacement, cross-file CSV schemas, and audio
conversion failure/success using a mocked converter. Geometry uses engine/GLM
stand-ins; Havok initialization and Papyrus install registration are source-only
contracts. Real GLM/Havok, xmake, ffmpeg and game integration remain separate.

Third full file review: full_third_review.py tests production FX filename parsing,
vanished-directory recovery, sparse scene-setting lookup, five-stage registry
initialization in normal/VR branches, and injected worker launch failure. Engine
methods/YAML are stand-ins; thread fault injection replaces only the thread type.
Real sklearn tests cover small/rare classes, independent export directories and
atomic INI publication failures. No Windows/game/VR integration is performed.
Training exports now live under out/models/run-*/ so merges use this run only.

Fourth full file review: full_fourth_review.py exercises the production async
consumer with real threads, deterministic shutdown and injected launch failure.
It uses C++23 move_only_function where available and a move-only callable stand-in
on Apple libc++ versions without it. Record string/view boundaries, write failures,
form parsing and furniture grid limits are behavioral tests. Theme publication and
physics retry wiring are source contracts; the existing AtomicWrite suite tests
replacement behavior separately. Furniture grids exceeding 256 samples per axis
are rejected, with at most 64 hit-skipping attempts per ray. No game runtime test.

Fifth full file review: full_fifth_review.py tests production voice condition
subset fallback, condition-matched legacy edits, missing-set creation and binary
threshold lookup against a linear reference (including duplicate priorities).
Voice metadata, absent tags and atomic export are source contracts; real yaml-cpp
and game execution remain separate. The actual audio rename script is exercised
in temporary directories for overlapping names, 120-file natural-order
idempotence, occupied targets, injected publication failure and failed rollback.
Publication uses filesystem hard links; unrecoverable rollback keeps staged bytes
and a manifest in the reported .voice-rename-* directory for manual recovery.

Sixth full file review: full_sixth_review.py extracts production Papyrus native
queries to test multi-action reverse lookups, the climax wildcard and invalid
indices, and reset success/error reporting. full_sixth_persistence.py exercises
legacy sexuality conversion across eight distributions, collapsed ranges, and
strict tracked-actor ordering. full_sixth_geometry.py tests actual transform and
furniture scan functions, signed/periodic tilt filtering in degrees, and correct
partner-pelvis sampling; ray casts and engine objects are stand-ins.
full_sixth_scripts.py executes a limited source-derived translation of selected
Papyrus helpers for phase indexing, lip restoration, statistics, bounded list
merging, trimming and tag replacement. The translation is not a Papyrus compiler
or VM; real script compilation, scheduling and game integration remain untested.

Seventh full file review: full_seventh_geometry.py extracts both production node
constructors to exercise vector growth without dangling parent references; the
actual BestFit/Segment/reference-segment methods verify root-to-tip orientation.
full_seventh_persistence.py exercises the real AtomicWrite header with exclusive
staging ownership, occupied paths, failed replacement and concurrent publishers,
and validates percentage boundaries in production statistics initialization and
settings normalization. full_seventh_review.py tests partner requirements across
candidate permutations, duplicate/null inputs and invalid totals.
full_seventh_scripts.py uses the existing limited Papyrus translator for ranked
partner limits and duplicate removal. REVIEW_BASE_DIR can select saved sources
from the start of the round while preserving earlier uncommitted changes. Tests
use engine/API stand-ins; no DLL, Papyrus VM or real game integration is implied.

Systematic audit: systematic_audit.py checks the actual Misc.h across two TUs,
missing/null script properties, creature fragment sex bits, None actor native
boundaries, weighted stage selection against every ticket of a reference model,
legacy segment geometry with randomized optimality checks, and the actual hash
CLI. systematic_scripts.py checks sparse climax positions, stage history/timers,
rejected scene reset recovery, tag filters, pathing flags, offset-array bounds
and canceled movement via the limited production-source translator. Full audit
coverage and remaining work are tracked separately in docs/logic-audit; passing
these tests is not a statement that all source or game behavior is verified.

Oct5 audit continuation: systematic_native.py extracts creature matching, legacy
interaction partner/graph guards, descriptor initialization, kissing-anchor guards,
repeated-stage history, reordered offset targets and degree-to-radian vector
setters. Snapshot invalidation order is a source contract, not an engine test.
systematic_scripts.py additionally covers sparse voice/expression paging and
backend shrink, reordered aliases, structural stage-tag comparisons and direct
stage-ID jumps, sex overrides, final overlay layers, bounded camera attempts and
inactive default definition data. full_sixth_persistence.py now checks bulk legacy
statistics use one snapshot and match individual conversions. decode_bounds.cpp
checks all 256 boolean byte values; only 0/1 are accepted. No VM, Windows ABI,
real ImGui, device/plugin or game scheduling integration is claimed.

Remaining source contracts (2026-10-05):
  contract_boundaries.py is included in run.py. Eight scoped groups exercise
  settings/theme fields, RaceID/score domains, SLR positions and four scene
  versions, actor-scoped temporary storage, both scaling branches, retained tag
  precedence and 64-bit assignment totals. Uses production headers/functions and
  engine stand-ins; the legacy SKEE cast is replaced by a common API stand-in.
  build_contracts.py is an opt-in Lua test requiring lupa and
  XMAKE_DEPEND_SOURCE=<xmake v2.9.5 modules/core/project/depend.lua>.
  It runs production Lua with the actual upstream dependency detector and mock
  compiler/filesystem/target. It does not run a Windows build or download code.
  Game/VM/ABI acceptance steps: docs/logic-audit/runtime-validation.md.

Current full-source audit additions:
  motion_presence.py compiles the actual NiMotion class, implementation and PCA
  with vector/node stand-ins. Tests valid world origin, missing/nonfinite samples,
  contiguous histories and ring wrap. actor_preparation_restore.py executes
  actual prepare/restore paths for original/new death, marker and owner state.
  REVIEW_BASE=HEAD reproduces their committed-source assertion failures.
  animation_graph_locks.py checks actual ReleaseAnimations using guards that
  reject duplicate/out-of-order acquisitions. This does not prove external lock order.
  hud_ownership.py checks script ownership/failure behavior plus the added native
  query, aggression setter and bounded positions. reposition_lifecycle.py exercises
  bounded/stale movement, Ending cleanup timeout and shared essential restoration.
  All are in run.py; VM/ABI/game verification remains separate.
