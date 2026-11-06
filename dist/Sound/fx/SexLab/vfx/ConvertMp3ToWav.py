import os
import shutil
import subprocess
import tempfile
import wave

def valid_wav(path):
  try:
    with wave.open(path, 'rb') as audio:
      frames = audio.getnframes()
      return frames > 0 and len(audio.readframes(frames)) == frames * audio.getnchannels() * audio.getsampwidth()
  except (OSError, EOFError, wave.Error):
    return False

def convert_mp3_to_wav(directory):
  for root, _, files in os.walk(directory):
    for file in files:
      if file.endswith(".mp3"):
        mp3_path = os.path.join(root, file)
        wav_path = os.path.splitext(mp3_path)[0] + ".wav"
        # An existing file may belong to a different recording; leave both intact.
        if os.path.exists(wav_path):
          continue
        with tempfile.TemporaryDirectory(prefix='sexlab-audio-', dir=root) as staging:
          temporary = os.path.join(staging, 'converted.wav')
          subprocess.run(["ffmpeg", "-nostdin", "-i", mp3_path, temporary], check=True)
          if not valid_wav(temporary):
            raise RuntimeError("Invalid conversion output: " + mp3_path)
          # Exclusive create prevents overwriting a file that appeared during conversion.
          created = False
          try:
            with open(temporary, 'rb') as source, open(wav_path, 'xb') as target:
              created = True
              shutil.copyfileobj(source, target)
            if not valid_wav(wav_path):
              raise RuntimeError("Invalid copied output: " + wav_path)
          except Exception:
            if created:
              os.remove(wav_path) # Only the output created exclusively by this attempt.
            raise
          os.remove(mp3_path)

if __name__ == "__main__":
  directory = os.path.dirname(os.path.abspath(__file__))
  convert_mp3_to_wav(directory)
