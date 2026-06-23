#!/usr/bin/env python3
"""
render_reel.py — レンダリング部品（⑤⑦）
- render_html_to_mp4(html, out): build_reel のHTMLを決定論フレーム書き出し→ffmpeg→MP4
  （尺は window.CFG.dur から自動取得。今回確立した「カクつかない」方式）
- image_to_clip(img, out, dur): カバー/ポスターを軽ズーム＋フェードの短尺クリップに
- concat_mp4s([...], out): SAR正規化してから連結（連結でハマった所の対策込み）
"""
import os, math, pathlib, subprocess
from playwright.sync_api import sync_playwright

INJECT = "*{transition:none!important;animation:none!important}#control{display:none!important}#replay{display:none!important}"

def render_html_to_mp4(html_path, out_path, fps=30, _max_frames=None):
    src = open(html_path).read().replace("</style>", INJECT + "</style>")
    rpath = html_path + ".render.html"; open(rpath, "w").write(src)
    fdir = out_path + "_frames"; os.makedirs(fdir, exist_ok=True)
    url = "file://" + str(pathlib.Path(rpath).resolve())
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        pg.goto(url); pg.evaluate("()=>document.fonts.ready"); pg.wait_for_timeout(300)
        dur = float(pg.evaluate("window.CFG ? window.CFG.dur : 50"))
        total = math.ceil(dur * fps)
        if _max_frames: total = min(total, _max_frames)
        for f in range(total):
            pg.evaluate("(t)=>window.renderAt(t)", f / fps)
            pg.screenshot(path=os.path.join(fdir, "f%05d.jpg" % f), type="jpeg", quality=92)
        b.close()
    subprocess.run(["ffmpeg", "-y", "-framerate", str(fps), "-i", os.path.join(fdir, "f%05d.jpg"),
        "-vf", "format=yuv420p", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path], check=True, capture_output=True)
    for fn in os.listdir(fdir): os.remove(os.path.join(fdir, fn))
    os.rmdir(fdir); os.remove(rpath)
    return out_path

def image_to_clip(img_path, out_path, dur=3.5, fps=30):
    n = int(dur * fps)
    vf = (f"scale=1080:1920:flags=lanczos,zoompan=z='1+0.05*on/{n-1}':d={n}:"
          f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps},"
          f"fade=t=in:st=0:d=0.3,fade=t=out:st={dur-0.35:.2f}:d=0.35,format=yuv420p")
    subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", img_path, "-t", str(dur), "-vf", vf,
        "-r", str(fps), "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-pix_fmt", "yuv420p", out_path], check=True, capture_output=True)
    return out_path

def concat_mp4s(clips, out_path, fps=30):
    inputs = []
    for c in clips: inputs += ["-i", c]
    n = len(clips)
    chains = "".join(f"[{i}:v]scale=1080:1920,setsar=1,fps={fps},format=yuv420p[v{i}];" for i in range(n))
    cat = "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v]"
    subprocess.run(["ffmpeg", "-y", *inputs, "-filter_complex", chains + cat, "-map", "[v]",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", out_path], check=True, capture_output=True)
    return out_path

# ---------- 効果音(オリジナル合成・上品/控えめ) ----------
import numpy as np, wave, shutil
_SR = 44100

def _sfx_write(path, sig):
    sig = np.clip(sig, -1, 1)
    pcm = (np.stack([sig, sig], axis=1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(_SR); w.writeframes(pcm.tobytes())

def _smooth(x, k=24): return np.convolve(x, np.ones(k) / k, "same")

def _synth_sfx(sfx_dir):
    os.makedirs(sfx_dir, exist_ok=True)
    done = os.path.join(sfx_dir, ".ok")
    if os.path.exists(done): return sfx_dir
    # chime: やわらかい鈴 (イントロ/CTA)
    n = int(_SR * 0.7); t = np.arange(n) / _SR; env = np.exp(-t / 0.22)
    sig = (np.sin(2*np.pi*784*t) + 0.6*np.sin(2*np.pi*1175*t) + 0.3*np.sin(2*np.pi*1568*t)) / 1.9
    sig *= env * 0.5; sig[:120] *= np.linspace(0, 1, 120)
    _sfx_write(os.path.join(sfx_dir, "chime.wav"), sig)
    # ding(キラン): 明るめの鈴 (棒グラフ/数字)
    n = int(_SR * 0.55); t = np.arange(n) / _SR; env = np.exp(-t / 0.16)
    sig = (np.sin(2*np.pi*1318*t) + 0.5*np.sin(2*np.pi*1976*t)) / 1.5
    sig *= env * 0.5; sig[:80] *= np.linspace(0, 1, 80)
    _sfx_write(os.path.join(sfx_dir, "ding.wav"), sig)
    # whoosh: ソフトな空気音 (チャート描画)
    n = int(_SR * 0.5); t = np.arange(n) / _SR
    env = np.sin(np.pi * t / (n / _SR)) ** 1.4
    sig = _smooth(np.random.randn(n), 40) * 0.5 * env * 0.4
    _sfx_write(os.path.join(sfx_dir, "whoosh.wav"), sig)
    # rise: 小さな上昇音 (setup)
    n = int(_SR * 0.4); t = np.arange(n) / _SR; f = 330 + 220 * (t / (n / _SR))
    sig = np.sin(2*np.pi*f*t) * np.sin(np.pi * t / (n / _SR)) * 0.3
    _sfx_write(os.path.join(sfx_dir, "rise.wav"), sig)
    open(done, "w").write("ok"); return sfx_dir

def tts(text, out_path, voice="ja-JP-NanamiNeural"):
    """edge-tts(無料・MS)でテキストを日本語音声(mp3)に。失敗時は例外。"""
    subprocess.run(["edge-tts", "--voice", voice, "--text", text, "--write-media", out_path],
                   check=True, capture_output=True, timeout=40)
    return out_path

def add_sfx(video_in, video_out, events, sfx_dir="/tmp/sfx", fps=30):
    """events=[(t_sec, name_or_path, vol), ...] を無音トラックに重ねて動画に焼く。
    name_or_path が実在ファイルならそれを、なければ sfx_dir/name.wav を使う。"""
    if not events:
        shutil.copy(video_in, video_out); return video_out
    _synth_sfx(sfx_dir)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", video_in], capture_output=True, text=True).stdout.strip() or 60)
    inp = ["-i", video_in, "-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=44100:cl=stereo"]
    filt = []; labels = ["[1]"]
    for k, (t, name, vol) in enumerate(events):
        src = name if os.path.exists(name) else os.path.join(sfx_dir, name + ".wav")
        inp += ["-i", src]
        ms = max(0, int(t * 1000))
        filt.append(f"[{2+k}]adelay={ms}|{ms},volume={vol}[e{k}]"); labels.append(f"[e{k}]")
    filt.append("".join(labels) + f"amix=inputs={len(events)+1}:duration=first:normalize=0[mix]")
    subprocess.run(["ffmpeg", "-y", *inp, "-filter_complex", ";".join(filt),
        "-map", "0:v", "-map", "[mix]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest",
        video_out], check=True, capture_output=True)
    return video_out

if __name__ == "__main__":
    import sys
    render_html_to_mp4(sys.argv[1], sys.argv[2], fps=int(sys.argv[3]) if len(sys.argv) > 3 else 30)
    print("rendered", sys.argv[2])
