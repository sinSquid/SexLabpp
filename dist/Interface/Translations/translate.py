import os
import tempfile
import shutil
from pathlib import Path
import sys

languages = [
  "CHINESE",
  "CZECH",
  "DANISH",
  # "ENGLISH",
  "FINNISH",
  "FRENCH",
  "GERMAN",
  "GREEK",
  "ITALIAN",
  "JAPANESE",
  "NORWEGIAN",
  "POLISH",
  "RUSSIAN",
  "SPANISH",
  "SWEDISH",
  "TURKISH"
]
translated_languages = [
  "RUSSIAN",
  "SPANISH"
]

def parse_file(file_path):
  lines = Path(file_path).read_text(encoding='utf-16le').splitlines(keepends=True)
  # A BOM is metadata, not part of the first translation key.
  if lines:
    lines[0] = lines[0].removeprefix("\ufeff")
  todo_keys = set()
  pending_todo = False
  for line in lines:
    if line.startswith("# TODO:"):
      marker = line[len("# TODO:"):].strip().split(maxsplit=1)
      if marker and marker[0].startswith('$'):
        todo_keys.add(marker[0])
        pending_todo = False
      else:
        pending_todo = True
    elif line.startswith('$'):
      if pending_todo:
        todo_keys.add(line.split(maxsplit=1)[0])
      pending_todo = False
  keys = {line.split(maxsplit=1)[0]: line for line in lines
          if line.startswith('$') and line.split(maxsplit=1)[0] not in todo_keys}
  return keys, lines


def copy_new_keys(file_path, en_lines):
  file_path = Path(file_path)
  l_keys, _ = parse_file(file_path) if file_path.exists() else ({}, [])
  result = []
  for line in en_lines:
    if line.startswith('$'):
      key = line.split(maxsplit=1)[0]
      if key in l_keys:
        result.append(l_keys[key])
      else:
        result.extend(("# TODO: " + key + "\n", line))
    else:
      result.append(line)
  # Finish rendering before touching the destination; replace on the same volume.
  temporary = None
  try:
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-16le',
                                    dir=file_path.parent, suffix='.tmp', delete=False) as output:
      temporary = Path(output.name)
      output.write('\ufeff' + ''.join(result))
    os.replace(temporary, file_path)
  finally:
    if temporary is not None:
      temporary.unlink(missing_ok=True)


def main():
  script_dir = Path(__file__).parent.resolve()
  translations_dir = script_dir if script_dir.name == "Translations" else script_dir / "Interface" / "Translations"
  english_files = sorted(translations_dir.glob("*ENGLISH.txt"))
  if len(english_files) != 1:
    print(f"Expected one ENGLISH.txt in {translations_dir}, found {len(english_files)}")
    return 1
  en_path = english_files[0]
  prefix = en_path.name.removesuffix("ENGLISH.txt")
  _, en_lines = parse_file(en_path)
  for language in languages:
    destination = translations_dir / (prefix + language + ".txt")
    print(f"Processing {destination}")
    if language in translated_languages:
      copy_new_keys(destination, en_lines)
    else:
      shutil.copyfile(en_path, destination)
  print("Done")
  return 0


if __name__ == '__main__':
  sys.exit(main())
