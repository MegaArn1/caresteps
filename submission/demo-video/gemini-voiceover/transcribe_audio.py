"""Local ASR for content checking and new word-level subtitle timing.
Run using the separate faster-whisper environment, not the app environment.
"""
import argparse
import json
from pathlib import Path
import time
from faster_whisper import WhisperModel

parser = argparse.ArgumentParser()
parser.add_argument('--wait', action='store_true')
parser.add_argument('--model', default='small.en')
args = parser.parse_args()
root = Path(__file__).resolve().parent / 'generated'
model = WhisperModel(args.model, device='cpu', compute_type='int8', cpu_threads=8,
                     download_root='/tmp/caresteps-tts-asr/models')
print('ASR model loaded', args.model, flush=True)
completed = set()
last_progress = time.monotonic()
while True:
    for index in range(35):
        name = f'full_{index:02}'
        audio = root / (name + '.wav')
        metadata = root / (name + '.json')
        output = root / (name + '.asr.json')
        if index in completed:
            continue
        if output.exists():
            completed.add(index); continue
        if not audio.exists() or not metadata.exists():
            continue
        segments, info = model.transcribe(str(audio), language='en', beam_size=5,
            word_timestamps=True, condition_on_previous_text=False,
            initial_prompt='CareSteps. Madam Tan. Amlodipine. WorkBuddy. API. PDF.')
        segments = list(segments)
        result = {
            'audio':audio.name, 'method':'faster-whisper/' + args.model,
            'language': info.language,
            'transcript': ''.join(s.text for s in segments).strip(),
            'words': [{'word': w.word.strip(), 'start': w.start, 'end': w.end,
                       'probability': w.probability} for s in segments for w in (s.words or [])],
            'note':'Automatic recognition; not a substitute for human assessment of voice preference.',
        }
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
        print(f'{index:02}: {result["transcript"]}', flush=True)
        completed.add(index);last_progress=time.monotonic()
    if len(completed) == 35 or not args.wait:
        break
    if time.monotonic()-last_progress > 600:
        print('Timed out waiting for remaining audio; completed',len(completed),flush=True);break
    time.sleep(2)
print('TRANSCRIBED', len(completed), flush=True)
