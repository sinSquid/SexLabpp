Portable regression suite
-------------------------
Run in WSL/Linux with Python 3 and a C++23 compiler:
  CXX=g++ python3 tests/run.py

The runner includes 47 entry points, including the 2026-10-31 lifecycle,
revert barrier, geometry, data persistence, Papyrus and UI regressions.

Additional tool regressions (Python environment with numpy, pandas,
scikit-learn, joblib and lupa):
  python tests/review_tooling_contracts.py
  python tests/model_export.py
  python tests/lua_audit.py
  python tests/spriggit_rule.py

Real GLM matrix regression (uses the local Xmake dependency cache):
  CXX=g++ python3 tests/raycast_transform.py

Lua syntax and XML escaping:
  python tests/lua_audit.py
Requires lupa. The earlier audit used a cached lupa 2.8 wheel installed only under
E:\code-lib\SexLabpp-audit-20261022\python-test-deps (not a game dependency).
The 2026-10-31 review uses an isolated environment under
E:\code-lib\SexLabpp-review-20261031\venv (not a game dependency).

Windows yaml-cpp persistence regression:
  python tests/strip_persistence.py <temporary-output.cpp>
Compile the emitted file with MSVC, /std:c++latest /EHsc /MD,
YAML_CPP_STATIC_DEFINE, src and yaml-cpp include paths, and yaml-cpp.lib.
Run the executable with an empty temporary data directory as its argument.

These tests execute production helpers with engine stand-ins, or real file/YAML
operations. They do not run Skyrim, Havok, Papyrus VM scheduling, or live rendering.
The test doubles and a successful compiler/linker result are not proof that every
repository path is free of logic or concurrency defects.
