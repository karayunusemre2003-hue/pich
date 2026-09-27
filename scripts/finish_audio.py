#!/usr/bin/env python3
"""Add documented music/SFX to a finished video without touching picture or input."""
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def run(args, capture=False):
    return subprocess.run(args, check=True, capture_output=capture, text=capture)


def probe(path):
    return json.loads(run(['ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', str(path)], True).stdout)


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def number(value, lo, hi, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError(f'{name} must be a finite number in [{lo}, {hi}]')
    return value


def asset(item):
    path = Path(item['file']).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f'audio missing: {path}')
    if not item.get('rights_checked') is True or not item.get('source_note', '').strip():
        raise ValueError(f'audio rights/source not confirmed: {path}')
    if not any(s['codec_type'] == 'audio' for s in probe(path)['streams']):
        raise ValueError(f'not audio: {path}')
    number(item['gain_db'], -60, 0, 'gain_db')
    return path


def finish(plan_path, output):
    plan = json.loads(plan_path.read_text())
    source = Path(plan['source']).expanduser().resolve()
    output = output.expanduser().resolve()
    qa = output.with_suffix('.sound-qa.json')
    if not source.is_file() or source == output or output.exists() or qa.exists():
        raise ValueError('missing input or output/QA already exists; never overwrite')
    music, cues = plan.get('music'), plan.get('sfx', [])
    if music is not None and (not isinstance(music, dict) or not music):
        raise ValueError('music must be a non-empty object or null')
    if not isinstance(cues, list) or len(cues) > 32:
        raise ValueError('invalid cue list')
    if music is None and not cues:
        raise ValueError('nothing to mix')
    data = probe(source)
    video = next((s for s in data['streams'] if s['codec_type'] == 'video'), None)
    voice = next((s for s in data['streams'] if s['codec_type'] == 'audio'), None)
    if video is None or voice is None:
        raise ValueError('input needs video + voice audio')
    duration = float(video.get('duration', data['format']['duration']))
    if duration <= 0:
        raise ValueError('invalid duration')
    before = sha256(source)
    cmd = ['ffmpeg', '-hide_banner', '-v', 'error', '-y', '-i', str(source)]
    graph = [f'[0:a]aresample=48000,atrim=duration={duration:.6f},asetpts=PTS-STARTPTS,apad=whole_dur={duration:.6f}[vo]']
    if music:
        graph.append('[vo]asplit=2[vo_mix][vo_sc]')
    inputs = ['[vo_mix]' if music else '[vo]']
    next_index = 1
    for i, item in enumerate(([music] if music else []) + cues):
        path = asset(item)
        if i == 0 and music:
            cmd += ['-stream_loop', '-1', '-i', str(path)]
            fadein = number(item.get('fade_in_s', .4), 0, duration, 'fade_in_s')
            fadeout = number(item.get('fade_out_s', 1.), 0, duration, 'fade_out_s')
            chain = f'aresample=48000,atrim=duration={duration:.6f},asetpts=PTS-STARTPTS,volume={item["gain_db"]}dB'
            if fadein:
                chain += f',afade=t=in:st=0:d={fadein:.6f}'
            if fadeout:
                chain += f',afade=t=out:st={duration-fadeout:.6f}:d={fadeout:.6f}'
            graph.append(f'[{next_index}:a]{chain},apad=whole_dur={duration:.6f}[bed]')
            graph.append('[bed][vo_sc]sidechaincompress=threshold=0.03:ratio=2:attack=15:release=250[duck]')
            inputs.append('[duck]')
        else:
            at = number(item['at_s'], 0, duration, 'at_s')
            if at >= duration:
                raise ValueError('at_s must be before the video ends')
            cmd += ['-i', str(path)]
            graph.append(f'[{next_index}:a]aresample=48000,volume={item["gain_db"]}dB,adelay=delays={round(at*1000)}:all=1,atrim=duration={duration:.6f},apad=whole_dur={duration:.6f}[fx{i}]')
            inputs.append(f'[fx{i}]')
        next_index += 1
    graph.append(''.join(inputs) + f'amix=inputs={len(inputs)}:duration=first:normalize=0,atrim=duration={duration:.6f},alimiter=limit=0.89125:level=0[out]')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=f'.{output.stem}-', suffix='.mp4', dir=output.parent, delete=False) as f:
        temp = Path(f.name)
    try:
        run(cmd + ['-filter_complex', ';'.join(graph), '-map', '0:v:0', '-map', '[out]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-t', f'{duration:.6f}', '-movflags', '+faststart', str(temp)])
        result = probe(temp)
        v = next(s for s in result['streams'] if s['codec_type'] == 'video')
        a = next(s for s in result['streams'] if s['codec_type'] == 'audio')
        if int(v['nb_read_frames']) != int(video['nb_read_frames']) or abs(float(v['duration']) - float(a['duration'])) > .07:
            raise RuntimeError('audio/video stream or frame-count QA failed')
        run(['ffmpeg', '-v', 'error', '-i', str(temp), '-f', 'null', '-'])
        stats = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(temp), '-vn', '-af', 'volumedetect', '-f', 'null', '-'], capture_output=True, text=True).stderr
        peaks = re.findall(r'max_volume:\s*([-\d.]+) dB', stats)
        peak = float(peaks[-1]) if peaks else None
        if peak is None or peak > -0.5:
            raise RuntimeError(f'decoded peak unsafe or unavailable: {peak} dBFS')
        if sha256(source) != before:
            raise RuntimeError('input hash changed')
        report = {'status': 'REVIEW (listening and platform rights outstanding)', 'input_sha256': before, 'input_unchanged': True,
                  'output_sha256': sha256(temp), 'frames': int(v['nb_read_frames']), 'audio_duration_s': float(a['duration']),
                  'video_duration_s': float(v['duration']), 'decoded_peak_dbfs': peak,
                  'music': {k: music.get(k) for k in ('file', 'source_note', 'license_url')} if music else None,
                  'sfx': [{k: c.get(k) for k in ('file', 'source_note', 'license_url', 'at_s')} for c in cues]}
        # Hard links create the final filename atomically; an existing file is never replaced.
        os.link(temp, output)
        try:
            with qa.open('x') as f:
                f.write(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
        except Exception:
            if output.exists() and output.stat().st_ino == temp.stat().st_ino:
                output.unlink()
            raise
        print(json.dumps(report, indent=2, ensure_ascii=False))
    finally:
        temp.unlink(missing_ok=True)


if __name__ == '__main__':
    try:
        if len(sys.argv) != 4:
            raise ValueError('usage: finish_audio.py plan.json input-video.mp4 output.mp4')
        p = Path(sys.argv[1]); conf = json.loads(p.read_text())
        if Path(conf.get('source', '')).expanduser().resolve() != Path(sys.argv[2]).expanduser().resolve():
            raise ValueError('plan source and input-video must match')
        finish(p, Path(sys.argv[3]))
    except (ValueError, KeyError, subprocess.CalledProcessError, RuntimeError) as exc:
        sys.exit(f'Error: {exc}')
