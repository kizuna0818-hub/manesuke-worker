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

if __name__ == "__main__":
    import sys
    render_html_to_mp4(sys.argv[1], sys.argv[2], fps=int(sys.argv[3]) if len(sys.argv) > 3 else 30)
    print("rendered", sys.argv[2])
