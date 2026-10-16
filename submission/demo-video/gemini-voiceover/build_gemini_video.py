"""Create a separate demo with the generated voice and new ASR-aligned subtitles.

Requires numpy/Pillow and ffmpeg. Preserves the original video and source audio.
Any longer speech receives a short hold on that scene's last frame, not sped-up audio.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import difflib
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import wave
import numpy as np

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
GEN = HERE / 'generated'
WORK = Path('/tmp/caresteps-gemini-render')
WORK.mkdir(exist_ok=True)
FINAL = BASE / 'caresteps-demo-gemini.mp4'
INPUT_VIDEO = BASE / 'source/raw.webm'
SEGMENTS = json.loads((HERE / 'segments.json').read_text())['segments']
RATE = 24000
FPS = 30


def run(cmd):
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-1800:])
    return result.stdout


def probe(path):
    return json.loads(run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)]))


def normalize(word):
    word = word.lower().replace('’', "'")
    replacements = {'145':'one hundred forty five','88':'eighty eight','14':'fourteen',
                    '21':'twenty one','995':'nine nine five','homepage':'home page',
                    'non-compliance':'noncompliance'}
    for source,target in replacements.items():
        word = re.sub(r'\b'+re.escape(source)+r'\b',target,word)
    return re.findall(r"[a-z]+(?:'[a-z]+)?",word)


def align_text(text, asr, head_trim, length):
    # Map the exact spoken script to recognized words, preserving original wording.
    original = text.split()
    expected=[];owners=[]
    for i,token in enumerate(original):
        normalized=normalize(token)
        expected.extend(normalized);owners.extend([i]*len(normalized))
    heard=[];stamps=[]
    for word in asr['words']:
        tokens=normalize(word['word'])
        for i,token in enumerate(tokens):
            heard.append(token)
            duration=word['end']-word['start']
            stamps.append((word['start']+duration*i/max(1,len(tokens)),
                           word['start']+duration*(i+1)/max(1,len(tokens))))
    matcher=difflib.SequenceMatcher(None,expected,heard,autojunk=False)
    mapping=[None]*len(expected)
    mismatches=[]
    for op,a,b,c,d in matcher.get_opcodes():
        if op=='equal':
            for x,y in zip(range(a,b),range(c,d)):
                mapping[x]=stamps[y]
        elif op in ('replace','delete'):
            left=stamps[c][0] if c<len(stamps) else stamps[-1][1]
            right=stamps[d-1][1] if d>c else left+.08
            for x in range(a,b):
                mapping[x]=(left+(right-left)*(x-a)/max(1,b-a),left+(right-left)*(x-a+1)/max(1,b-a))
            mismatches.append({'type':op,'script':expected[a:b],'recognized':heard[c:d]})
        elif op=='insert':
            mismatches.append({'type':op,'script':[],'recognized':heard[c:d]})
    aligned=[]
    previous=0.0
    for i,token in enumerate(original):
        ts=[mapping[k] for k,o in enumerate(owners) if o==i and mapping[k] is not None]
        if not ts:
            start=previous;end=min(length,start+.12)
        else:
            start=max(previous,ts[0][0]-head_trim,0)
            end=min(length,max(start+.01,ts[-1][1]-head_trim))
        aligned.append({'word':token,'start':start,'end':end})
        previous=start
    return aligned,mismatches,matcher.ratio()


def srt_time(t):
    ms=round(t*1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'


def ass_time(t):
    cs=round(t*100)
    return f'{cs//360000:01}:{cs//6000%60:02}:{cs//100%60:02}.{cs%100:02}'


def captions_for(words, start_time):
    groups=[];group=[]
    for word in words:
        candidate=' '.join(x['word'] for x in group+[word])
        if group and (len(candidate)>88 or word['end']-group[0]['start']>6.2):
            groups.append(group);group=[]
        group.append(word)
        if re.search(r'[.!?]$',word['word']) and len(' '.join(x['word'] for x in group))>38:
            groups.append(group);group=[]
    if group:groups.append(group)
    cues=[]
    for i,g in enumerate(groups):
        start=max(0,g[0]['start']-.05)
        end=g[-1]['end']+.16
        if i+1<len(groups):end=min(end,groups[i+1][0]['start']-.01)
        end=max(start+.25,end)
        cues.append((start_time+start,start_time+end,' '.join(x['word'] for x in g)))
    return cues


def main():
    processed=GEN/'processed';processed.mkdir(exist_ok=True)
    timeline=[];audio_parts=[];subtitles=[];position_frames=0
    for seg in SEGMENTS:
        i=int(seg['id']);stem=f'full_{i:02}'
        metadata=json.loads((GEN/(stem+'.json')).read_text())
        asr=json.loads((GEN/(stem+'.asr.json')).read_text())
        with wave.open(str(GEN/(stem+'.wav')),'rb') as w:
            assert (w.getframerate(),w.getnchannels(),w.getsampwidth())==(RATE,1,2)
            samples=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float64)/32768
        active=np.flatnonzero(np.abs(samples)>10**(-48/20))
        assert active.size, f'No audible signal: {stem}'
        head=max(0,int(active[0]-.05*RATE))
        tail=min(len(samples),int(active[-1]+.12*RATE))
        clean=samples[head:tail].copy()
        # Constant gain per segment; no compression or speed changes.
        spoken=clean[np.abs(clean)>10**(-48/20)]
        rms=np.sqrt(np.mean(spoken**2))
        gain=min(10**(-20/20)/rms,10**(-3/20)/max(np.max(np.abs(clean)),1e-9))
        clean*=gain
        audio=np.rint(clean*32767).astype('<i2')
        duration=len(audio)/RATE
        old_duration=seg['window_seconds']
        frames=math.ceil(max(old_duration,duration+.35)*FPS)
        start=position_frames/FPS
        window=frames/FPS
        position_frames+=frames
        with wave.open(str(processed/f'voice_{i:02}.wav'),'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(RATE);w.writeframes(audio.tobytes())
        aligned,differences,ratio=align_text(metadata['spoken_text_requested'],asr,head/RATE,duration)
        cues=captions_for(aligned,start)
        subtitles.extend(cues)
        audio_parts.append((start,audio))
        timeline.append({
            'id':seg['id'],'title':seg['title'],'original_start_ms':seg['timeline_start_ms'],
            'original_end_ms':seg['timeline_end_ms'],'new_start_seconds':start,
            'new_end_seconds':start+window,'frames':frames,'original_window_seconds':old_duration,
            'extra_hold_seconds':round(window-old_duration,6),'audio_duration_seconds':duration,
            'head_trim_seconds':head/RATE,'tail_trim_seconds':(len(samples)-tail)/RATE,
            'constant_gain_db':20*math.log10(gain),'time_stretch_applied':False,
            'asr_match_ratio':ratio,'asr_differences':differences,
            'requested_text':metadata['spoken_text_requested'],'aligned_words':aligned,
        })
    duration=position_frames/FPS
    assert 300<=duration<=480
    track=np.zeros(round(duration*RATE),dtype='<i2')
    for start,data in audio_parts:
        offset=round(start*RATE)
        assert offset+len(data)<=len(track)
        assert not np.any(track[offset:offset+len(data)])
        track[offset:offset+len(data)]=data
    narration=GEN/'narration_full.wav'
    with wave.open(str(narration),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(RATE);w.writeframes(track.tobytes())
    # Preview uses three complete segments, separated by 0.6 s of silence.
    audition=np.concatenate([piece for i in (0,19,33) for piece in (audio_parts[i][1],np.zeros(round(.6*RATE),dtype='<i2'))])
    with wave.open(str(GEN/'audition-kore.wav'),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(RATE);w.writeframes(audition.tobytes())
    run(['ffmpeg','-v','error','-y','-i',str(GEN/'audition-kore.wav'),'-c:a','libmp3lame','-b:a','192k',str(BASE/'caresteps-voice-preview.mp3')])
    (GEN/'edit_timeline.json').write_text(json.dumps(timeline,indent=2)+'\n')
    # Padding both sides of adjacent cues can overlap by a few frames. Clamp
    # every cue against the next cue's actual padded start before rendering.
    subtitles=[(a,min(b,subtitles[i+1][0]-.02) if i+1<len(subtitles) else b,text)
               for i,(a,b,text) in enumerate(subtitles)]
    assert all(b>a for a,b,_ in subtitles)
    assert all(subtitles[i][1]<=subtitles[i+1][0] for i in range(len(subtitles)-1))
    srt=BASE/'caresteps-demo-gemini.en.srt'
    srt.write_text(''.join(f'{i}\n{srt_time(a)} --> {srt_time(b)}\n{text}\n\n' for i,(a,b,text) in enumerate(subtitles,1)))
    ass=WORK/'captions.ass'
    ass.write_text('[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 0\n'
       '\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n'
       'Style: Default,DejaVu Sans,32,&H00FFFFFF,&H00FFFFFF,&H00111827,&H00111827,0,0,0,0,100,100,0,0,1,1,0,2,100,100,30,1\n'
       '\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'+
       ''.join(f'Dialogue: 0,{ass_time(a)},{ass_time(b)},Default,,0,0,0,,{text}\n' for a,b,text in subtitles))
    (BASE/'caresteps-demo-gemini.chapters.txt').write_text('\n'.join(f"{int(s['new_start_seconds'])//60:02}:{int(s['new_start_seconds'])%60:02} {s['title']}" for s in timeline)+'\n')
    (GEN/'spoken_script.md').write_text('# Gemini TTS: requested and checked narration\n\n'
        'The only text expansion from the original is Mdm Tan → Madam Tan for pronunciation. '
        'Automatic ASR may miss a weak final consonant; differences are retained in edit_timeline.json.\n\n'+
        '\n\n'.join(f"## {s['id']} — {s['title']}\n\n{s['requested_text']}" for s in timeline)+'\n')
    raw_duration=float(probe(INPUT_VIDEO)['format']['duration'])
    original_duration=SEGMENTS[-1]['timeline_end_ms']/1000
    time_scale=original_duration/raw_duration
    def render_scene(scene):
        idx=int(scene['id']);dest=WORK/f'scene_{idx:02}.mp4'
        raw_start=scene['original_start_ms']/1000/time_scale
        raw_length=scene['original_window_seconds']/time_scale
        filters=(f'setpts={time_scale:.12f}*(PTS-STARTPTS),fps={FPS},'
                 'scale=1742:980,pad=1920:1080:89:0:color=0x111827,'
                 f'tpad=stop_mode=clone:stop_duration={scene["extra_hold_seconds"]+.2:.6f}')
        run(['ffmpeg','-v','error','-y','-ss',f'{raw_start:.9f}','-t',f'{raw_length:.9f}',
             '-i',str(INPUT_VIDEO),'-an','-vf',filters,'-frames:v',str(scene['frames']),
             '-c:v','libx264','-preset','veryfast','-crf','18','-threads','3','-pix_fmt','yuv420p',str(dest)])
        return idx
    print('Prepared narration and new captions; duration',duration,'seconds. Rendering 35 scenes.',flush=True)
    if '--reuse-scenes' in sys.argv:
        for scene in timeline:
            cached=WORK/f"scene_{int(scene['id']):02}.mp4"
            info=probe(cached)
            assert int(info['streams'][0]['nb_frames'])==scene['frames'], 'Cached scene duration differs'
        print('Reusing verified scene videos for subtitle-only edit',flush=True)
    else:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(render_scene,s) for s in timeline]
            for f in as_completed(futures):print('Rendered scene',f.result(),flush=True)
    concat=WORK/'scenes.txt'
    concat.write_text(''.join(f"file '{WORK/f'scene_{i:02}.mp4'}'\n" for i in range(35)))
    print('Encoding final video',flush=True)
    run(['ffmpeg','-v','warning','-y','-f','concat','-safe','0','-i',str(concat),'-i',str(narration),
         '-vf',f'ass={ass}','-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p',
         '-r','30','-threads','6','-c:a','aac','-b:a','128k','-ar','48000','-ac','2',
         '-af','loudnorm=I=-16:TP=-2:LRA=11','-t',str(duration),'-movflags','+faststart',str(FINAL)])
    verification=probe(FINAL)
    verification.update({'requested_model':'gemini-3.8-flash-tts','voice':'Kore',
        'provider_host':'api.tiantoken.com','endpoint':'/v1beta/models/gemini-3.8-flash-tts:generateContent',
        'backend_identity_independently_verified':False,'audio_segments':35,'speech_time_stretched':False,
        'subtitle_method':'Local faster-whisper/small.en word timing aligned to supplied narration',
        'natural_voice_preference':'Requires user listening; no subjective listening score claimed.',
        'sha256':hashlib.sha256(FINAL.read_bytes()).hexdigest()})
    (BASE/'caresteps-demo-gemini.verification.json').write_text(json.dumps(verification,indent=2)+'\n')
    print('FINISHED',FINAL,duration,'seconds',FINAL.stat().st_size,'bytes',flush=True)

if __name__=='__main__':main()
