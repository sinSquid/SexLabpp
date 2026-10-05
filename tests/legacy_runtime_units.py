"""Execute production Papyrus runtime arithmetic with a seconds-based native stand-in.

This verifies local control flow and units, not Papyrus compilation or VM execution.
REVIEW_BASE=HEAD tests the committed script instead.
"""
from types import SimpleNamespace

from full_sixth_scripts import Array, helper


def main():
    durations = {"fixed": 2.5, "dynamic": 0.0, "last": 1.25}
    registry = SimpleNamespace(
        GetPathMax=lambda registry, stage: Array(durations),
        GetFixedLength=lambda registry, stage: durations[stage],
    )
    runtime = helper("sslBaseAnimation", "GetTimersRunTime", "StageTimers", {
        "Registry": "scene", "SexLabRegistry": registry})
    assert runtime(Array([10.0, 20.0])) == 23.75
    assert runtime(Array([10.0, 20.0, 30.0])) == 23.75
    assert runtime(Array([10.0])) == -1.0
    durations.clear()
    durations.update({"one": 0.0, "two": 0.0, "three": 0.0})
    assert runtime(Array([1.0, 2.0])) == 5.0
    durations.clear()
    assert runtime(Array([1.0, 2.0])) == 0.0
    print("PASS: legacy runtime keeps native seconds and dynamic timer fallback")


if __name__ == "__main__":
    main()
