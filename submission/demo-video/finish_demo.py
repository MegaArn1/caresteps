"""Time narration to the real browser recording and export an accessible MP4."""

import json
import os
import subprocess
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = Path(os.environ.get('DEMO_WORK_DIR', str(HERE / 'source')))
SCRIPT = json.loads((WORK / 'script.json').read_text(encoding='utf-8'))
ACTUAL = json.loads((WORK / 'actual_times.json').read_text(encoding='utf-8'))
OUTPUT = HERE / 'caresteps-demo.mp4'


def srt_time(seconds):
    millis = int(round(seconds * 1000))
    return f'{millis // 3600000:02}:{millis // 60000 % 60:02}:{millis // 1000 % 60:02},{millis % 1000:03}'


def subtitle_parts(text, max_chars=95):
    words = text.split()
    parts = []
    part = ''
    for word in words:
        next_part = (part + ' ' + word).strip()
        if len(next_part) > max_chars and part:
            parts.append(part)
            part = word
        else:
            part = next_part
    if part:
        parts.append(part)
    if len(parts) > 1 and len(parts[-1].split()) < 4:
        tail = parts.pop().split()
        while len(tail) < 4 and len(parts[-1].split()) > 5:
            words = parts[-1].split()
            tail.insert(0, words.pop())
            parts[-1] = ' '.join(words)
        parts.append(' '.join(tail))
    return parts


def main():
    track = []
    sample_rate = None
    for entry in ACTUAL:
        with wave.open(str(WORK / 'voice' / f"voice_{entry['index']:02}.wav"), 'rb') as wav:
            assert wav.getnchannels() == 1 and wav.getsampwidth() == 2, 'Expected mono 16-bit speech'
            if sample_rate is None:
                sample_rate = wav.getframerate()
            assert wav.getframerate() == sample_rate, 'Narration sample rates differ'
            track.append((entry, wav.readframes(wav.getnframes())))
    # Each utterance is placed at the exact time the real browser action started.
    audio = bytearray(int((ACTUAL[-1]['endMs'] / 1000 + 2) * sample_rate * 2))
    for entry, data in track:
        start = int(entry['startMs'] / 1000 * sample_rate) * 2
        assert start + len(data) <= len(audio)
        audio[start:start + len(data)] = data
    with wave.open(str(WORK / 'narration.wav'), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(audio)

    cues = []
    for entry in ACTUAL:
        text = SCRIPT[entry['index']]['voice']
        parts = subtitle_parts(text)
        words = [len(p.split()) for p in parts]
        total = sum(words)
        voice_duration = entry['voiceSeconds']
        elapsed = 0
        for part, count in zip(parts, words):
            start = entry['startMs'] / 1000 + elapsed
            elapsed += voice_duration * count / total
            stop = entry['startMs'] / 1000 + elapsed
            cues.append((start, stop, part))
    (WORK / 'captions.srt').write_text(''.join(
        f'{i}\n{srt_time(start)} --> {srt_time(stop)}\n{line}\n\n'
        for i, (start, stop, line) in enumerate(cues, 1)
    ), encoding='utf-8')
    (HERE / 'NARRATION.md').write_text(
        '# CareSteps demo narration\n\n'
        'English narration and subtitles accompany the real browser recording. '
        'All patients shown are fictional. The live model turn and limited-mode fallback '
        'are recorded from separate local demo databases.\n\n' +
        '\n\n'.join(f"## {e['title']}\n\n{e['voice']}" for e in SCRIPT) + '\n',
        encoding='utf-8',
    )
    raw_duration = float(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(WORK / 'raw.webm'),
    ], text=True).strip())
    # Playwright's video timestamps drift slightly against the operation clock.
    # Bring the video onto the same wall-clock timeline used by narration and captions.
    time_scale = ACTUAL[-1]['endMs'] / 1000 / raw_duration
    command = [
        'ffmpeg', '-hide_banner', '-y', '-loglevel', 'warning', '-i', str(WORK / 'raw.webm'),
        '-i', str(WORK / 'narration.wav'), '-vf',
        f"setpts={time_scale:.9f}*PTS,scale=1742:980,"
        f"pad=1920:1080:89:0:color=0x111827,"
        f"subtitles={WORK / 'captions.srt'}:force_style='FontName=DejaVu Sans,"
        f"FontSize=10,PrimaryColour=&H00FFFFFF,OutlineColour=&H00111827,"
        f"Outline=0.5,Alignment=2,MarginV=18'",
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p',
        '-r', '30', '-c:a', 'aac', '-b:a', '128k', '-ar', '48000', '-ac', '2',
        '-af', 'loudnorm=I=-16:TP=-2:LRA=11',
        '-movflags', '+faststart', '-shortest', str(OUTPUT),
    ]
    print('Encoding', OUTPUT, flush=True)
    subprocess.run(command, check=True)
    print('Finished', OUTPUT, 'bytes:', OUTPUT.stat().st_size, flush=True)


if __name__ == '__main__':
    main()
