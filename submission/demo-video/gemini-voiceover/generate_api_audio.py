"""Generate authorized TTS audio. Credentials are read with getpass, never stored.

Run with a terminal, enter the key when prompted, then send JSON commands on stdin:
  {"op":"generate","indices":[0],"voice":"shimmer","prefix":"sample"}
  {"op":"generate","indices":[0,1,2],"voice":"shimmer","prefix":"full"}
  {"op":"quit"}
Set TTS_API_HOST to your authorized gateway hostname. No redirects are followed.
"""
import getpass
import os
import base64
import io
import wave
import hashlib
import http.client
import json
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
OUT = HERE / 'generated'
OUT.mkdir(exist_ok=True)
SEGMENTS = json.loads((HERE / 'segments.json').read_text())['segments']
HOST = os.environ.get('TTS_API_HOST', 'gateway.example')
ENDPOINT = '/v1/audio/speech'
MODEL = 'gemini-3.8-flash-tts'


def probe(path):
    return json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_entries',
        'format=duration,size:stream=codec_name,sample_rate,channels', '-of', 'json', str(path)
    ], stderr=subprocess.DEVNULL, text=True))


def generate(key, index, command):
    seg = SEGMENTS[index]
    voice = command.get('voice', 'shimmer')
    model = command.get('model', MODEL)
    prefix = command.get('prefix', 'full')
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', prefix):
        raise ValueError('Invalid prefix')
    text = command.get('text') or seg['text'].replace('Mdm Tan', 'Madam Tan')
    protocol = command.get('protocol', 'speech')
    endpoint = ENDPOINT
    if protocol == 'native':
        if not re.fullmatch(r'[a-zA-Z0-9._-]+', model):
            raise ValueError('Invalid model identifier')
        endpoint = f'/v1beta/models/{model}:generateContent'
        payload = {
            'contents': [{'parts': [{'text': text}]}],
            'generationConfig': {'responseModalities': ['AUDIO'],
                'speechConfig': {'voiceConfig': {'prebuiltVoiceConfig': {'voiceName': voice}}}},
        }
    elif protocol == 'interactions':
        endpoint = '/v1beta/interactions'
        payload = {'model': model, 'input': [{'type': 'user_input', 'content': [{
            'type': 'text', 'text': text, 'annotations': [{'type': 'speech_metadata',
            'style': command.get('style', 'Warm, clear and composed product presentation. Natural international English.')}]
        }]}], 'response_format': {'type': 'audio'},
        'generation_config': {'speech_config': [{'voice': voice}]}}
    else:
        payload = {'model': model, 'input': text, 'voice': voice, 'speed': command.get('speed', 1)}
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    name = f'{prefix}_{index:02}'
    meta_path = OUT / f'{name}.json'
    if meta_path.exists():
        old = json.loads(meta_path.read_text())
        if old.get('request_sha256') == fingerprint and (OUT / old['filename']).exists():
            print(json.dumps({'cached': True, **old}), flush=True)
            return
        raise ValueError(f'{name} exists with another request; use a different prefix')
    request_start = time.monotonic()
    conn = http.client.HTTPSConnection(HOST, timeout=120)
    try:
        conn.request('POST', endpoint, body=json.dumps(payload).encode(), headers={
            'Authorization': 'Bearer ' + key,
            'New-Api-User': '1', 'Content-Type': 'application/json',
        })
        response = conn.getresponse()
        content_type = response.getheader('Content-Type', '')
        body = response.read()
        status = response.status
    finally:
        conn.close()
    if status == 200 and protocol in ('native', 'interactions'):
        data = json.loads(body)
        chunks = []
        if protocol == 'native':
            for candidate in data.get('candidates', []):
                for part in candidate.get('content', {}).get('parts', []):
                    inline = part.get('inlineData', {})
                    if inline.get('data') and inline.get('mimeType', '').startswith('audio/'):
                        chunks.append(inline)
        else:
            for step in data.get('steps', []):
                if step.get('type') == 'model_output':
                    for part in step.get('content', []):
                        if part.get('type') == 'audio' and part.get('data'):
                            chunks.append({'mimeType': part.get('mime_type', 'audio/wav'), 'data': part['data']})
        if chunks:
            mime = chunks[0]['mimeType']
            body = b''.join(base64.b64decode(chunk['data']) for chunk in chunks)
            if 'L16' in mime.upper() or 'pcm' in mime.lower():
                rate_match = re.search(r'rate=(\d+)', mime)
                rate = int(rate_match.group(1)) if rate_match else 24000
                output = io.BytesIO()
                with wave.open(output, 'wb') as wav:
                    wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(rate); wav.writeframes(body)
                body = output.getvalue()
            content_type = mime
    if status != 200 or 'json' in content_type or body[:1] == b'{':
        message = body[:2000].decode('utf-8', errors='replace').replace(key, '[redacted]')
        message = re.sub(r'sk-[A-Za-z0-9_-]+', '[redacted]', message)
        print(json.dumps({'error': True, 'status': status, 'content_type': content_type,
                          'body': message, 'index': index, 'model_requested': model}), flush=True)
        return False
    temporary = OUT / (name + '.download')
    temporary.write_bytes(body)
    try:
        info = probe(temporary)
    except subprocess.CalledProcessError:
        print(json.dumps({'error': True, 'message': 'HTTP 200 body is not decodable audio',
                          'content_type': content_type, 'bytes': len(body)}), flush=True)
        return False
    codec = info['streams'][0]['codec_name']
    suffix = '.wav' if codec.startswith('pcm_') else { 'mp3': '.mp3', 'aac': '.aac', 'opus': '.ogg' }.get(codec, '.audio')
    audio = OUT / (name + suffix)
    temporary.rename(audio)
    metadata = {
        'index': index, 'filename': audio.name, 'provider_host': HOST,
        'model_requested': model, 'voice_requested': voice, 'speed_requested': payload.get('speed'), 'protocol': protocol, 'endpoint': endpoint,
        'spoken_text_requested': text, 'source_text': seg['text'],
        'request_sha256': fingerprint, 'response_content_type': content_type,
        'latency_seconds': round(time.monotonic() - request_start, 3),
        'duration_seconds': float(info['format']['duration']), 'bytes': len(body),
        'sample_rate_hz': int(info['streams'][0]['sample_rate']),
        'channels': int(info['streams'][0]['channels']), 'codec': codec,
        'audio_sha256': hashlib.sha256(body).hexdigest(),
        'original_window_seconds': seg['window_seconds'],
        'backend_model_identity_independently_verified': False,
    }
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'generated': True, **metadata}), flush=True)
    return True


def main():
    key = getpass.getpass('TTS API key (hidden; memory only): ')
    if not key:
        raise SystemExit('No key supplied')
    print('READY: send a JSON command; key is not persisted.', flush=True)
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            command = json.loads(line)
            if command.get('op') == 'quit':
                break
            if command.get('op') == 'models':
                conn = http.client.HTTPSConnection(HOST, timeout=30)
                conn.request('GET', '/v1/models', headers={'Authorization': 'Bearer ' + key})
                response = conn.getresponse()
                data = json.loads(response.read()); conn.close()
                print(json.dumps({'status': response.status, 'audio_models': [m.get('id') for m in data.get('data', []) if re.search(r'tts|speech|audio', m.get('id', ''), re.I)]}), flush=True)
                continue
            if command.get('op') != 'generate':
                raise ValueError('Unknown operation')
            for index in command['indices']:
                if not isinstance(index, int) or not 0 <= index < len(SEGMENTS):
                    raise ValueError('Invalid segment index')
                if generate(key, index, command) is False:
                    print('BATCH_STOPPED_ON_ERROR', flush=True)
                    break
            print('READY', flush=True)
        except Exception as exc:
            # Avoid dumping requests, headers, key or full exception arguments.
            print(json.dumps({'error': True, 'type': type(exc).__name__}), flush=True)
    key = ''


if __name__ == '__main__':
    main()
