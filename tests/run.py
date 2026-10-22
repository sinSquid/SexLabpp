"""Run the portable native-source regressions (Python 3 + C++23 compiler)."""
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
TESTS=(
    'fork_review_regressions.py', 'arrow_speed_hotkeys.py',
    'ring_buffer.py', 'tracking_records.py', 'tag_sets.py', 'raycast_boundaries.py',
    'scene_registration_owner.py',
    'papyrus_base_contracts.py',
    'theme_save.py',
    'statistics_roundtrip.py', 'graph_paths.py', 'input_helpers.py',
    'voice_cache.py', 'geometry_math.py', 'settings_access.py', 'speed_graph_bounds.py', 'decode_bounds.py', 'expression_sampling.py', 'settings_ini.py', 'bed_query.py',
)
for test in TESTS:
    print('RUN',test,flush=True)
    subprocess.run([sys.executable,str(ROOT/test)],check=True)
print('PASS: all portable regression entry points')
