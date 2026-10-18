import json,wave,pathlib,sys,subprocess,math,struct
root=pathlib.Path.cwd(); rec=root/'.data/recording'; out=root/'output'
timeline=json.loads((rec/'timeline.json').read_text()); segments=timeline['segments']
with wave.open(segments[0]['file'],'rb') as first: params=first.getparams()
rate=params.framerate; sample_width=params.sampwidth; channels=params.nchannels
target=out/'Orma-Voiceover.wav'
with wave.open(str(target),'wb') as dest:
    dest.setparams(params); frame=0
    for seg in segments:
        wanted=round(seg['start_ms']*rate/1000)
        if wanted>frame: dest.writeframes(b'\0'*((wanted-frame)*sample_width*channels)); frame=wanted
        with wave.open(seg['file'],'rb') as clip:
            if clip.getparams()[:3]!=params[:3]: raise RuntimeError('Audio formats differ')
            data=clip.readframes(clip.getnframes()); dest.writeframes(data); frame+=clip.getnframes()
    end=round(timeline['duration_ms']*rate/1000)
    if end>frame: dest.writeframes(b'\0'*((end-frame)*sample_width*channels))
texts={s['id']:s['text'] for s in json.loads((root/'.data/narration/segments.json').read_text())}
def stamp(value):
    ms=round(value*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'
subtitles=[];i=0
for seg in segments:
    words=texts[seg['id']].split(); total=len(words)
    for j in range(0,total,12):
        part=words[j:j+12];i+=1
        a=seg['start_ms']/1000+seg['duration']*j/total
        b=seg['start_ms']/1000+seg['duration']*min(j+12,total)/total
        subtitles.append(f'{i}\n{stamp(a)} --> {stamp(b)}\n{" ".join(part)}\n')
srt=out/'Orma-Captions.srt';srt.write_text('\n'.join(subtitles),encoding='utf-8')
sys.path.insert(0,str(root/'.data/video-deps'))
import imageio_ffmpeg
ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
cmd=[ffmpeg,'-hide_banner','-loglevel','warning','-y','-i',str(rec/'walkthrough.webm'),'-i',str(target),'-i',str(srt),'-map','0:v:0','-map','1:a:0','-map','2:s:0','-c:v','libx264','-preset','veryfast','-crf','22','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-c:s','mov_text','-metadata:s:s:0','language=eng','-movflags','+faststart','-shortest',str(out/'Orma-Demo-Narrated.mp4')]
subprocess.run(cmd,check=True)
print(json.dumps({'video':str(out/'Orma-Demo-Narrated.mp4'),'seconds':timeline['duration_ms']/1000,'voice':'Microsoft David Desktop (synthetic)','audio_rate':rate}))
