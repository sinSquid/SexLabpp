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
