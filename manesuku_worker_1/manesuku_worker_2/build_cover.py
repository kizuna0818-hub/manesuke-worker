#!/usr/bin/env python3
"""
build_cover.py — マネスク カバー生成（⑥）
方針: 背景アートはAI(fal.ai)、**数字は実データをHTMLで重ねる**（誤記ゼロ）。

  from build_cover import make_cover
  make_cover(cover_spec, "cover.png", bg_prompt="...", size=(1080,1350))

cover_spec の数字は build_data の headline から作る（実数のみ）。
fal.ai が使えない環境では自動でkintsugi調のフォールバック背景を生成する。
"""
import os, pathlib, subprocess
from playwright.sync_api import sync_playwright

COVER_CSS = r'''
:root{--cream:#F2EBDD;--cream-dim:#B9B2A2;--gold:#E2B45C;--gold-soft:#F3D79A;--red:#E27A5C;
 --jp:"Noto Sans JP",system-ui,sans-serif;--mono:"Roboto Mono",monospace;}
*{margin:0;padding:0;box-sizing:border-box}
html,body{margin:0}
.cv{position:relative;width:var(--W);height:var(--H);overflow:hidden;font-family:var(--jp);color:var(--cream);
  background:#0B0B0F center/cover no-repeat;--u:calc(var(--H)/100);--w:calc(var(--W)/100);}
.cv .bg{position:absolute;inset:0;background:var(--BG) center/cover no-repeat}
.cv .scrim{position:absolute;inset:0;background:
  radial-gradient(120% 70% at 50% 8%,rgba(226,180,92,.16),transparent 55%),
  linear-gradient(180deg,rgba(7,7,10,.72) 0%,rgba(7,7,10,.30) 32%,rgba(7,7,10,.55) 70%,rgba(7,7,10,.92) 100%)}
.cv .frame{position:absolute;inset:calc(var(--u)*2.4);border:1px solid rgba(226,180,92,.45);border-radius:calc(var(--u)*2)}
.cv .pad{position:absolute;inset:0;padding:calc(var(--u)*7) calc(var(--u)*6);display:flex;flex-direction:column}
.eyebrow{font-size:calc(var(--u)*3);letter-spacing:.18em;color:var(--gold);font-weight:900}
.chip{display:inline-block;margin-left:calc(var(--u)*2);border:1px solid rgba(226,180,92,.5);border-radius:999px;
  padding:calc(var(--u)*.6) calc(var(--u)*2.2);font-size:calc(var(--u)*2.2);color:var(--gold-soft);font-weight:700}
.title{margin-top:calc(var(--u)*4);font-weight:900;line-height:1.18;font-size:calc(var(--u)*6.2);
  text-shadow:0 calc(var(--u)*.4) calc(var(--u)*2) rgba(0,0,0,.6)}
.title .hl{color:var(--gold)}
.spacer{flex:1}
.result{display:flex;align-items:baseline;gap:calc(var(--u)*2.5);flex-wrap:wrap}
.big{font-family:var(--mono);font-weight:700;color:var(--gold);font-size:calc(var(--w)*11);line-height:1.02;white-space:nowrap;
  text-shadow:0 0 calc(var(--u)*5) rgba(226,180,92,.4)}
.mult{font-weight:900;font-size:calc(var(--w)*6);color:var(--cream);margin-top:calc(var(--u)*0.6)}
.lead{font-size:calc(var(--u)*3.2);color:var(--cream-dim);font-weight:700;margin-bottom:calc(var(--u)*1)}
.chips{margin-top:calc(var(--u)*3);display:flex;gap:calc(var(--u)*2.5)}
.chips span{font-family:var(--mono);font-weight:700;font-size:calc(var(--w)*2.8);color:var(--cream);
  background:rgba(13,12,16,.55);border:1px solid rgba(255,255,255,.12);border-radius:calc(var(--u)*1.4);
  padding:calc(var(--u)*1) calc(var(--u)*2.4)}
.foot{margin-top:calc(var(--u)*4);display:flex;justify-content:space-between;align-items:flex-end;gap:calc(var(--u)*3)}
.handle{color:var(--gold);font-weight:900;font-size:calc(var(--w)*3);white-space:nowrap}
.note{font-size:calc(var(--w)*1.8);color:var(--cream-dim);line-height:1.5;max-width:54%;text-align:right}
'''

def cover_html(spec, bg_url, size=(1080,1350)):
    W,H = size
    chips = "".join(f"<span>{c}</span>" for c in spec.get("chips",[]))
    chip = f'<span class="chip">{spec["chip"]}</span>' if spec.get("chip") else ""
    return f'''<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700;900&family=Roboto+Mono:wght@500;700&display=swap" rel="stylesheet">
<style>{COVER_CSS}</style></head>
<body><div class="cv" style="--W:{W}px;--H:{H}px;--BG:url('{bg_url}')">
  <div class="bg"></div><div class="scrim"></div><div class="frame"></div>
  <div class="pad">
    <div><span class="eyebrow">マネスク</span>{chip}</div>
    <div class="title">{spec["title"]}</div>
    <div class="spacer"></div>
    <div class="lead">{spec.get("lead","")}</div>
    <div class="big">{spec["big"]}</div>
    <div class="mult">{spec.get("mult","")}</div>
    <div class="chips">{chips}</div>
    <div class="foot"><div class="handle">{spec.get("handle","")}</div><div class="note">{spec.get("note","")}</div></div>
  </div>
</div></body></html>'''

def render_png(html_path, out_png, size=(1080,1350)):
    url = "file://" + str(pathlib.Path(html_path).resolve())
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox"])
        pg = b.new_page(viewport={"width":size[0],"height":size[1]})
        pg.goto(url); pg.evaluate("()=>document.fonts.ready"); pg.wait_for_timeout(350)
        pg.screenshot(path=out_png)
        b.close()
    return out_png

def fallback_bg(out_path, size=(1080,1350)):
    """fal.ai が無い時のkintsugi調フォールバック背景。"""
    from PIL import Image, ImageDraw, ImageFilter
    W,H = size; im = Image.new("RGB",(W,H),(11,11,15))
    top=(28,22,12); bot=(7,7,10)
    px=im.load()
    for y in range(H):
        t=y/H
        px_row=tuple(int(top[i]*(1-t)+bot[i]*t) for i in range(3))
        for x in range(W): px[x,y]=px_row
    glow=Image.new("L",(W,H),0); gd=ImageDraw.Draw(glow)
    gd.ellipse([W*0.1,-H*0.2,W*0.9,H*0.45],fill=120)
    glow=glow.filter(ImageFilter.GaussianBlur(160))
    gold=Image.new("RGB",(W,H),(226,180,92))
    im=Image.composite(gold,im,glow.point(lambda v:int(v*0.45)))
    im.save(out_path,quality=92); return out_path

def gen_bg(prompt, out_path, size=(1080,1350)):
    """fal.ai で文字なし背景アートを生成（best-effort）。失敗時 fallback。"""
    key = os.environ.get("FAL_KEY")
    if key:
        try:
            import requests
            r = requests.post("https://fal.run/fal-ai/flux/schnell",
                headers={"Authorization":f"Key {key}","Content-Type":"application/json"},
                json={"prompt":prompt,"image_size":{"width":size[0],"height":size[1]}}, timeout=60)
            url = r.json()["images"][0]["url"]
            img = requests.get(url, timeout=60).content
            open(out_path,"wb").write(img); return out_path
        except Exception:
            pass
    return fallback_bg(out_path, size)

def make_cover(spec, out_png, bg_prompt=None, size=(1080,1350)):
    bg = out_png + ".bg.jpg"
    gen_bg(bg_prompt or "dark cinematic financial background, gold light, coins, subtle, no text, no words",
           bg, size)
    hp = out_png + ".html"; open(hp,"w").write(cover_html(spec, "file://"+str(pathlib.Path(bg).resolve()), size))
    render_png(hp, out_png, size)
    return out_png

if __name__ == "__main__":
    # テスラの実数から作るカバー（数字は build_data headline 由来）
    spec = {
      "chip":"TESLA ・ 7年",
      "title":'もし7年前に<br><span class="hl">TESLA株</span>を100万円分<br>買っていたら？',
      "lead":"2019年6月 → 2026年6月",
      "big":"約4,000万円", "mult":"≒ 40倍",
      "chips":["$15 → $400","¥100万 → ¥4,024万"],
      "handle":"@Money_school1515",
      "note":"※過去の実績であり将来を保証しません。投資助言ではありません。"
    }
    make_cover(spec, "cover_feed.png", size=(1080,1350))
    make_cover(spec, "cover_reel.png", size=(1080,1920))
    print("OK cover_feed.png / cover_reel.png")
