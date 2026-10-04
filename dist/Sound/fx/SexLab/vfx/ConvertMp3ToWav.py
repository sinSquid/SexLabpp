import os
from pathlib import Path
import subprocess
import tempfile


def convert_mp3_to_wav(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            if not file.lower().endswith('.mp3'):
                continue
            mp3_path = Path(root) / file
            wav_path = mp3_path.with_suffix('.wav')
            # An existing output does not prove this source was converted.
            if wav_path.exists():
                continue
            with tempfile.TemporaryDirectory(prefix='.wav-convert-', dir=root) as temp:
                output = Path(temp) / wav_path.name
                subprocess.run(['ffmpeg', '-i', str(mp3_path), str(output)], check=True)
                if not output.is_file() or output.stat().st_size == 0:
                    raise RuntimeError(f'Conversion produced no audio: {mp3_path}')
                os.replace(output, wav_path)
            mp3_path.unlink()


if __name__ == '__main__':
    convert_mp3_to_wav(Path(__file__).resolve().parent)
