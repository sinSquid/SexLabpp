"""Execute production PSC calculations with engine stand-ins, not the Skyrim VM.

--baseline-ref HEAD demonstrates fractional enjoyment being lost before the fix.
"""
import argparse
import ast
from functools import cache
from pathlib import Path
import subprocess
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--baseline-ref')
args = parser.parse_args()

# Reuse the existing strict PSC executor without running its unrelated tests.
helper = ROOT / 'tests/papyrus_confirmed_regressions.py'
tree = ast.parse(helper.read_text(encoding='utf-8'))
tree.body = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef))]
scope = {}
exec(compile(tree, str(helper), 'exec'), scope)
scope['TYPES'] = r'(?:bool|int|float|string|Actor|Form|Sound|ObjectReference|Alias|ssl\w+)'


@cache
def source(name):
    path = f'dist/Source/Scripts/{name}.psc'
    if args.baseline_ref:
        return subprocess.check_output(['git', 'show', f'{args.baseline_ref}:{path}'], cwd=ROOT).decode('utf-8')
    return (ROOT / path).read_text(encoding='utf-8')


scope['source'] = source
execute, body, Array = scope['execute'], scope['body'], scope['Array']
env = dict(_Config=NS(EnjRaiseMultInter=.8, NoStaminaEndsScene=False, DebugMode=False, GameRequiredOnHighEnj=False),
           _ActorRef='horse', _PlayerRef='player', _raceID=1, _arousalBase=0., _ModEnjMult=1.,
           _PainInterCur=0., _PainLevel=0., _PainApplied=0., _victim=False, _FullEnjoyment=0,
           _EnjoymentRemainder=0., _LoopEnjoymentDelay=0., _EnjoymentDelay=.8, UPDATE_INTERVAL=.8,
           _Thread=NS(ElementUI_EnjBars=True, CONSENT_CONNONSUB=0), ToInt=int,
           PapyrusUtil=NS(ClampInt=lambda value, lo, hi: max(lo, min(value, hi)),
                         ClampFloat=lambda value, lo, hi: max(lo, min(value, hi))))


def call(script, name, **kwargs):
    # The existing executor cannot parse an int cast on a zero-argument call.
    text = body(script, name).replace('CalcEnjoymentAndPainDelta() as int', 'ToInt(CalcEnjoymentAndPainDelta())')
    value, result = execute(text, dict(env, **kwargs))
    for key in list(env):
        if key.startswith('_') and key in result:
            env[key] = result[key]
    return value


flags = Array([False] * 30)
env['sslSystemConfig'] = NS(GetEnjoymentFactors=lambda: Array([5.] * 30))
env['CalcInterVelocityFactor'] = lambda *a: 1.5
base = call('sslThreadModel', 'CalcInteractionFactor', akPosition='horse', interActive=flags)
env['_EnjFactor'] = call('sslActorAlias', 'CalcContextEnjFactor', SameSexThread=False, WithLover=False)
env['_CurrentInteractions'] = flags
env['EnjFindConSubStatusMult'] = lambda: 1.
for name in ('CalcInteractionEnjoymentInst', 'CalcEnjoymentAdjusted', 'CalcEnjoymentAndPainDelta'):
    env[name] = lambda name=name: call('sslActorAlias', name)
env['CalcPainAdjusted'] = lambda: 0.
env['UpdateArousalStat'] = lambda: None


def simulate(factor, count=100, initial=0):
    env['_Thread'].CalcInteractionFactor = lambda *a: factor
    env['_InterFactor'] = factor
    env.update(_FullEnjoyment=initial, _EnjoymentRemainder=0., _LoopEnjoymentDelay=0., _PainLevel=0., _PainApplied=0.)
    for _ in range(count):
        call('sslActorAlias', 'UpdateEffectiveEnjoymentCalculations')
    return env['_FullEnjoyment']


value = simulate(base)
assert 29 <= value <= 30, f'fractional creature enjoyment lost: after 100 updates expected ~30, got {value}'
print('PASS: real PSC update chain accumulates 0.3 per update without interactions')
assert simulate(2.) == 100
assert abs(env['_EnjoymentRemainder']) < 1e-6
assert simulate(base, initial=-20) in (9, 10)
assert simulate(-base) in (-29, -30)
assert simulate(-2.) == -100 and abs(env['_EnjoymentRemainder']) < 1e-6
print('PASS: normal growth, zero crossing, negative increments and both clamps')

env.update(_EnjoymentRemainder=.75, _PainLevel=3., _PainApplied=3.)
call('sslActorAlias', 'SetEnjoyment', aiSet=0)
assert env['_FullEnjoyment'] == 0 and env['_EnjoymentRemainder'] == 0
env['_EnjoymentRemainder'] = .75
call('sslActorAlias', 'ResetEnjoymentVariables')
assert env['_FullEnjoyment'] == 0 and env['_EnjoymentRemainder'] == 0
print('PASS: explicit set and scene reset clear fractional state')
