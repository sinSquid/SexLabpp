"""Seventh-review script logic tests, using the limited Papyrus translator.

The extracted production statements run against Python API stand-ins. This does
not compile Papyrus or validate game/VM behavior. REVIEW_BASE_DIR selects saved
production sources from before this round, without discarding uncommitted work.
"""
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import full_sixth_scripts as scripts


def source(name):
    root = Path(os.environ.get('REVIEW_BASE_DIR', scripts.ROOT))
    return (root / 'dist/Source/Scripts' / f'{name}.psc').read_text()


def test_top_partners():
    for totals in ([], [8, 3], [3, 9, 1, 6, 8, 2, 10], [1, 3, 3, 2]):
        actors = list(range(len(totals)))
        for maximum in (-3, 0, 1, 2, len(totals), len(totals) + 2):
            calls = []

            def times_met(player, actor):
                assert 0 <= actor < len(totals)
                calls.append(actor)
                return totals[actor]

            query = scripts.helper('sslActorStats', 'MostUsedPlayerSexPartners', 'MaxActors=5', {
                'Game': SimpleNamespace(GetPlayer=lambda: 'player'),
                'SexLabStatistics': SimpleNamespace(
                    GetAllEncounters=lambda player: scripts.Array(actors), GetTimesMet=times_met),
                'Utility': SimpleNamespace(CreateIntArray=lambda size: scripts.Array([0] * size)),
                'PapyrusUtil': SimpleNamespace(ActorArray=lambda size: scripts.Array([None] * size)),
            })
            actual = query(maximum)
            limit = min(max(maximum, 0), len(actors))
            # The existing insertion sort breaks ties by later input position.
            expected = sorted(actors, key=lambda actor: (totals[actor], actor), reverse=True)[:limit]
            assert actual == expected, (totals, maximum, actual, expected)
            assert len(set(actual)) == len(actual)
            assert len(calls) == (len(actors) if limit else 0)


def test_duplicate_removal():
    remove = scripts.helper('sslUtility', 'RemoveDupesFromList', 'List, Removing, PreventAll=True', {
        'sslUtility': SimpleNamespace(AnimationArray=lambda size: scripts.Array([None] * size)),
    })
    cases = [(None, None, True, None), (None, ['A'], False, None),
             (['A'], None, False, ['A']), ([], ['A'], False, []),
             (['A'], [], False, ['A']),
             (['A', 'B'], ['A', 'A'], False, ['B']),
             (['A', 'A', 'B'], ['A'], False, ['B']),
             (['A', 'B'], ['A', 'A'], True, ['B']),
             (['A', 'A'], ['A'], True, ['A', 'A']),
             (['A', 'A'], ['A'], False, []),
             (['A', None, 'B', 'A', 'C'], ['A', None, None], False, ['B', 'C']),
             (['A', 'B', 'A', 'C'], ['X', 'X'], False, ['A', 'B', 'A', 'C']),
             ([None, None], [None], True, [None, None]),
             ([None, None], [None], False, [])]
    for original, removing, prevent, expected in cases:
        left = None if original is None else scripts.Array(original)
        right = None if removing is None else scripts.Array(removing)
        actual = remove(left, right, prevent)
        assert actual == expected, (original, removing, prevent, actual, expected)
        assert left == original and right == removing, 'must preserve input arrays'


if __name__ == '__main__':
    failures = []
    with patch.object(scripts, 'source', side_effect=source):
        for test in (test_top_partners, test_duplicate_removal):
            try:
                test()
                print(f'PASS: {test.__name__} (translated Papyrus, API stand-ins)')
            except Exception as error:
                failures.append(test.__name__)
                print(f'FAIL: {test.__name__}: {type(error).__name__}: {error}')
    if failures:
        raise SystemExit(f'Failed: {", ".join(failures)}')
    print('PASS: seventh-round script regressions; Papyrus compilation/game VM were not tested')
