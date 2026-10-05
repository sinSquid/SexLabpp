"""Portable behavior tests; game/DLL/Papyrus runtime validation is separate."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='sexlab-tests-') as tmp:
    for name in ('assignment_matching','request_sequence','core_utilities','decode_bounds'):
        binary=Path(tmp)/name
        subprocess.run([os.environ.get('CXX','clang++'),'-std=c++20','-O2','-pthread',str(ROOT/'tests'/f'{name}.cpp'),'-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)
for name in ('overlay_interaction_text', 'legacy_runtime_units', 'papyrus_project_xml', 'voice_export_publication', 'voice_creation_boundaries', 'script_property_boundaries', 'interaction_state_capacity', 'shared_snapshot_release', 'windows_file_stems', 'expression_numeric_range', 'round_eighth_regressions', 'collision_controller_restore', 'world_revert', 'collision_foot_ik', 'motion_presence', 'actor_preparation_restore', 'hud_ownership', 'reposition_lifecycle', 'legacy_input_boundaries', 'animation_graph_locks', 'animation_slot_boundaries', 'thread_access_boundaries', 'ui_voice_boundaries', 'proxy_allocation_boundaries', 'collision_physics_restore', 'creature_count_boundaries', 'object_bound_validity', 'transform_boundaries', 'actor_query_boundaries', 'default_bedroll', 'theme_editor', 'furniture_reachability', 'scene_partners', 'translation_regressions', 'contract_boundaries', 'systematic_audit', 'systematic_native', 'systematic_scripts', 'full_seventh_review','full_seventh_persistence','full_seventh_geometry','full_seventh_scripts','full_sixth_review','full_sixth_persistence','full_sixth_geometry','full_sixth_scripts','full_fifth_review','full_fourth_review','full_third_review','full_second_review','full_review_regressions','ml_session_regressions','strip_regressions','source_regressions','recognition_regressions','lifecycle_regressions','csv_schema','native_contracts','ml_export'):
    subprocess.run([sys.executable,str(ROOT/'tests'/f'{name}.py')],check=True)
print('PASS: all portable tests; DLL and game runtime were not tested')
