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
