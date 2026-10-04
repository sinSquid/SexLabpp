import os
import json
import re
from pathlib import Path
import shutil
import tempfile


def _rename_subfolder(profile_name, subfolder):
    files = sorted(
        (p for p in subfolder.iterdir() if p.is_file() and p.suffix.lower() in {'.mp3', '.wav'}),
        key=lambda p: (tuple(int(part) if part.isdigit() else part
                             for part in re.split(r'(\d+)', p.name.casefold())), p.name),
    )
    plan = [(source, subfolder / f'{profile_name}_{subfolder.name[0]}{index:02d}{source.suffix.lower()}')
            for index, source in enumerate(files, 1)]
    plan = [(source, target) for source, target in plan if source != target]
    if not plan:
        return
    sources = {source for source, _ in plan}
    for source, target in plan:
        if target.exists() and target not in sources and not target.samefile(source):
            raise FileExistsError(f'Rename target already exists: {target}')

    # Stage the entire permutation first, so one rename cannot destroy another
    # input. Keep staged bytes until every destination has been published.
    staging = Path(tempfile.mkdtemp(prefix='.voice-rename-', dir=subfolder))
    moved, published = [], []
    try:
        (staging / 'manifest.json').write_text(json.dumps([
            {'staged': str(index), 'source': source.name, 'target': target.name}
            for index, (source, target) in enumerate(plan)
        ], ensure_ascii=False, indent=2), encoding='utf-8')
        for index, (source, target) in enumerate(plan):
            temporary = staging / str(index)
            source.rename(temporary)
            moved.append((source, temporary, target))
        for source, temporary, target in moved:
            os.link(temporary, target)  # Exclusive publication; never replace an existing path.
            published.append((source, temporary, target))
    except Exception as error:
        recovery_errors = []
        for _, temporary, target in reversed(published):
            try:
                if target.exists() and target.samefile(temporary):
                    target.unlink()
            except OSError as failure:
                recovery_errors.append(str(failure))
        for source, temporary, _ in moved:
            try:
                os.link(temporary, source)
            except OSError as failure:
                recovery_errors.append(str(failure))
        if recovery_errors:
            raise RuntimeError(f'Rename failed; preserved recovery files in {staging}: {recovery_errors}') from error
        shutil.rmtree(staging)
        raise
    shutil.rmtree(staging)
    for source, _, target in moved:
        print(f'Renamed: {source} to {target}')


def rename_files_in_directory(directory):
    for profile in sorted(Path(directory).iterdir()):
        if profile.is_dir():
            for subfolder in sorted(profile.iterdir()):
                if subfolder.is_dir():
                    _rename_subfolder(profile.name, subfolder)


if __name__ == '__main__':
    rename_files_in_directory(Path(__file__).resolve().parent)
