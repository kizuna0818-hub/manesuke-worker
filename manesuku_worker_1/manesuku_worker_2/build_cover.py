#!/usr/bin/env python3
"""build_cover.py — マネスク 表紙(明るい・タイトル主役のバナー)。
タイトル(フック)を大きく中央に。利益額/ROIは載せない(動画で見せる)。
spec: {title, entryLabel, investLabel, verb}
"""
import pathlib
from playwright.sync_api import sync_playwright

def _dw(t):  # 表示幅の概算(英数=0.56, 和文=1.0)
    return sum(0.56 if (c.isascii()) else 1.0 for c in t)

def cover_html(s, size=(1080, 1920)):
    W, H = size
    w = max(_dw(s["title"]) + 1.0, _dw(s["investLabel"]))
    big = 8.6 if w <= 5.2 else (7.4 if w <= 6.6 else 6.4)
    css="""
*{margin:0;padding:0;box-sizing:border-box}
:root{--ink:#241F18;--dim:#8A7C63;--gold:#A9781F;--golds:#C79A3A;--red:#C73E22;--jp:"Noto Sans JP",system-ui,sans-serif;--W:__W__px;--H:__H__px;--u:calc(var(--H)/100)}
.cv{position:relative;width:var(--W);height:var(--H);overflow:hidden;font-family:var(--jp);color:var(--ink);
 background:linear-gradient(157deg,#FCF8EF 0%,#F5EAD3 56%,#EEDCB8 100%)}
.cv .deco{position:absolute;inset:0;background:radial-gradient(72% 42% at 50% 47%,rgba(226,180,92,.30),transparent 62%)}
.cv .frame{position:absolute;inset:calc(var(--u)*2.4);border:2px solid rgba(169,120,31,.5);border-radius:calc(var(--u)*2)}
.pad{position:absolute;inset:0;padding:calc(var(--u)*7) calc(var(--u)*4);display:flex;flex-direction:column;align-items:center;text-align:center}
.brand{font-size:calc(var(--u)*3);font-weight:900;color:var(--gold);letter-spacing:.32em}
.title{flex:1;display:flex;flex-direction:column;justify-content:center;gap:calc(var(--u)*1.2)}
.l1{font-size:calc(var(--u)*4.4);font-weight:800;color:var(--dim);white-space:nowrap}
.l2{font-size:calc(var(--u)*__BIG__);font-weight:900;line-height:1.12;color:var(--gold);white-space:nowrap}
.l2 .p{color:var(--ink)}
.l3{font-size:calc(var(--u)*__BIG__);font-weight:900;line-height:1.12;color:var(--red);white-space:nowrap}
.l4{font-size:calc(var(--u)*6.2);font-weight:900;color:var(--ink);margin-top:calc(var(--u)*.6)}
.teaser{font-size:calc(var(--u)*4.2);font-weight:900;color:var(--gold);letter-spacing:.04em;
 border:2px solid rgba(169,120,31,.55);border-radius:999px;padding:calc(var(--u)*1.4) calc(var(--u)*4)}
"""
    css=css.replace("__W__",str(W)).replace("__H__",str(H)).replace("__BIG__",str(big))
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body><div class="cv"><div class="deco"></div><div class="frame"></div><div class="pad"><div class="brand">マネスク</div><div class="title"><div class="l1">もし {s["entryLabel"]} {s.get("particle","に")}</div><div class="l2">{s["title"]}<span class="p">を</span></div><div class="l3">{s["investLabel"]}</div><div class="l4">{s["verb"]}</div></div><div class="teaser">今いくら…？</div></div></div></body></html>'

def make_cover(spec, out_png, series=None, size=(1080,1920)):
    spec.setdefault("verb","買ってたら"); spec.setdefault("particle","に")
    p=pathlib.Path("_cover_tmp.html"); p.write_text(cover_html(spec,size),encoding="utf-8")
    with sync_playwright() as pw:
        b=pw.chromium.launch(args=["--no-sandbox"]); pg=b.new_page(viewport={"width":size[0],"height":size[1]})
        pg.goto("file://"+str(p.resolve())); pg.evaluate("()=>document.fonts.ready"); pg.wait_for_timeout(250)
        pg.screenshot(path=out_png); b.close()
    return out_png
