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

script_dir = Path(__file__).parent.resolve()
if script_dir.name == "Translations":
  translations_dir = script_dir
else:
  translations_dir = script_dir / "Interface" / "Translations"

if not translations_dir.exists():
  print(f"Error: Could not find Translations directory at {translations_dir}")
  sys.exit(1)

f_english = list(translations_dir.glob("*ENGLISH.txt"))
if not f_english:
  print(f"Missing ENGLISH.txt in {translations_dir}")
  sys.exit(1)

en_path = f_english[0]
f_raw = en_path.name.replace("ENGLISH.txt", "")

def parse_file(file_path):
  encoding = 'utf-16' if file_path.read_bytes().startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-16le'
  with open(file_path, 'r', encoding=encoding, newline='') as file:
    lines = file.readlines()
  todo_keys = {lines[i+1].split(maxsplit=1)[0] for i, line in enumerate(lines) if line.startswith("# TODO:") and i+1 < len(lines)}
  keys = {line.split(maxsplit=1)[0]: line for line in lines if line.startswith('$') and line.split(maxsplit=1)[0] not in todo_keys}
  return keys, lines

_, en_lines = parse_file(en_path)

def copy_new_keys(file_path):
  l_keys, _ = parse_file(file_path)
  raw = file_path.read_bytes()
  encoding = 'utf-16be' if raw.startswith(b'\xfe\xff') else 'utf-16le'
  bom = raw[:2] if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else b''
  newline = '\r\n' if any(line.endswith('\r\n') for line in en_lines) else '\n'
  merged = []
  for line in en_lines:
    # A source TODO describes its English entry, not an existing local translation.
    if line.startswith('# TODO:'):
      continue
    if line.startswith('$'):
      key = line.split(maxsplit=1)[0]
      if key in l_keys:
        translated = l_keys[key]
        merged.append(translated if translated.endswith(('\n', '\r')) else translated + newline)
      else:
        merged.append("# TODO: " + key + newline)
        merged.append(line)
    else:
      merged.append(line)
  file_path.write_bytes(bom + ''.join(merged).encode(encoding))

for l in languages:
  new_path = translations_dir / (f_raw + l + ".txt")
  print(f"Processing {new_path}")
  if new_path.exists():
    print(f"Copying new keys to {l}")
    copy_new_keys(new_path)
    continue
  shutil.copyfile(en_path, new_path)

print("Done")
