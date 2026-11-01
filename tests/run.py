"""Run the portable native-source regressions (Python 3 + C++23 compiler)."""
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
TESTS=(
    'setup_watchdog.py',
    'review_creation_lifecycle.py', 'review_thread_cleanup.py', 'review_revert_barrier.py',
    'review_geometry_contracts.py',
    'review_native_data_core.py', 'review_native_data_contracts.py',
    'review_native_data_entrypoints.py', 'review_native_data_persistence.py',
    'review_native_data_recency.py', 'review_native_data_selection.py',
    'review_papyrus_contracts.py', 'review_papyrus_objects.py',
    'review_papyrus_lifecycle.py', 'review_papyrus_ui.py',
    'publication_rollback.py', 'geometry_binding.py',
    'compat_native.py', 'compat_assignment.py', 'compat_equipment.py',
    'audit_runtime.py', 'audit_papyrus.py', 'ini_merge.py', 'tag_log_views.py',
    'collision_physics_restore.py', 'collision_controller_restore.py', 'collision_foot_ik.py',
    'fork_review_regressions.py', 'arrow_speed_hotkeys.py', 'camera_control_cleanup.py',
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
