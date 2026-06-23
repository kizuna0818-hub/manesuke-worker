#!/usr/bin/env python3
"""
worker.py — マネスク Reel レンダーワーカー（FastAPI）
n8n から叩く。scenario→実データ、spec→完成MP4。

エンドポイント:
  GET  /health
  POST /build-data  {scenario}            -> {data} | 422 {needsReview}
  POST /produce     {spec, introUrl?, fps?} -> {jobId}（非同期）
  GET  /job/{id}                          -> {status, mp4? , error?}
  GET  /file/{name}                       -> 生成物(MP4)を返す

ローカル起動:  uvicorn worker:app --host 0.0.0.0 --port 8080
"""
import os, uuid, threading, traceback, urllib.request, subprocess
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

import build_data, build_reel, render_reel, build_cover, research

OUT = os.environ.get("OUT_DIR", "/tmp/out")
os.makedirs(OUT, exist_ok=True)

app = FastAPI(title="Manesuku Reel Worker")
JOBS = {}  # jobId -> {status, mp4|error}

class ScenarioReq(BaseModel):
    scenario: dict

class ProduceReq(BaseModel):
    spec: dict
    introUrl: Optional[str] = None   # 指定時は自分のバナーURLを優先
    cover: Optional[dict] = None     # 指定時は表紙を自動生成して頭に付ける
    fps: int = 30

@app.get("/health")
def health():
    return {"ok": True}

class ResearchReq(BaseModel):
    asset: str
    entryDate: str
    market: str = "us"

@app.post("/research")
def research_ep(req: ResearchReq):
    """②a: 個別株の分割調整後アンカー＋出来事＋出典（Claude＋web検索）。"""
    try:
        return {"research": research.research_single_stock(req.asset, req.entryDate, market=req.market)}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))   # needsReview → 止める
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/build-data")
def build_data_ep(req: ScenarioReq):
    """scenario -> 検証済み実データ（数字はここでしか作らない）"""
    try:
        return {"data": build_data.build_data(req.scenario)}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))   # needsReview等は止める
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _sfx_events(spec, offset, has_intro):
    """ビート構成から上品・控えめな効果音イベントを作る。"""
    ev = []
    if has_intro:
        ev.append((0.15, "chime", 0.5))          # 表紙で軽いチャイム
    t = float(offset)
    for b in spec.get("beats", []):
        typ = b.get("type"); d = float(b.get("dur", 3))
        if typ == "setup":
            ev.append((t + 0.1, "rise", 0.32))
        elif typ == "chart":
            ev.append((t + 0.15, "whoosh", 0.38)) # 描画開始
        elif typ == "bars":
            ev.append((t + 0.2, "ding", 0.5))      # 数字・棒グラフ
        elif typ == "cta":
            ev.append((t + 0.1, "chime", 0.4))
        t += d                                     # lesson/highlight は鳴らさない
    return ev

def _produce(job_id, spec, intro_url, fps, cover=None):
    try:
        html = build_reel.build(spec)
        hpath = os.path.join(OUT, f"{job_id}.html"); open(hpath, "w").write(html)
        reel = os.path.join(OUT, f"{job_id}_reel.mp4")
        render_reel.render_html_to_mp4(hpath, reel, fps=fps)
        silent = os.path.join(OUT, f"{job_id}_silent.mp4")
        intro_img = None; narr = None; cover_dur = 3.5
        if intro_url:                                   # 自分のバナーURL優先(読み上げなし)
            intro_img = os.path.join(OUT, f"{job_id}_intro.png")
            urllib.request.urlretrieve(intro_url, intro_img)
        elif cover:                                     # 表紙を自動生成 ＋ タイトル読み上げ
            intro_img = os.path.join(OUT, f"{job_id}_cover.png")
            build_cover.make_cover(cover, intro_img)
            try:                                        # TTS失敗時はスキップして続行
                text = f"もし{cover.get('title','')}を{cover.get('investLabel','')}{cover.get('verb','')}"
                narr = os.path.join(OUT, f"{job_id}_narr.mp3")
                render_reel.tts(text, narr)
                nd = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                    "format=duration", "-of", "default=nw=1:nk=1", narr],
                    capture_output=True, text=True).stdout.strip() or 0)
                cover_dur = max(3.5, nd + 0.8)          # 読み上げが終わるまで表紙を表示
            except Exception:
                narr = None
        if intro_img:
            intro_clip = os.path.join(OUT, f"{job_id}_intro.mp4")
            render_reel.image_to_clip(intro_img, intro_clip, dur=cover_dur, fps=fps)
            render_reel.concat_mp4s([intro_clip, reel], silent, fps=fps)
            offset = cover_dur
        else:
            os.replace(reel, silent); offset = 0.0
        final = os.path.join(OUT, f"{job_id}.mp4")
        events = _sfx_events(spec, offset, bool(intro_img))
        if narr:
            events.append((0.35, narr, 1.0))           # 表紙の上にナレーション
        render_reel.add_sfx(silent, final, events, sfx_dir=os.path.join(OUT, "sfx"), fps=fps)
        JOBS[job_id] = {"status": "done", "mp4": f"/file/{job_id}.mp4"}
    except Exception as e:
        JOBS[job_id] = {"status": "error", "error": str(e), "trace": traceback.format_exc()[-1000:]}

@app.post("/produce")
def produce(req: ProduceReq):
    """spec -> 完成MP4（非同期）。jobIdを返すのでポーリング。"""
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"status": "processing"}
    threading.Thread(target=_produce, args=(job_id, req.spec, req.introUrl, req.fps, req.cover), daemon=True).start()
    return {"jobId": job_id, "status": "processing"}

class CoverReq(BaseModel):
    coverSpec: dict
    width: int = 1080
    height: int = 1920

@app.post("/cover")
def cover_ep(req: CoverReq):
    """表紙(タイトルカード)PNGを生成して返す（単体テスト用）"""
    name = uuid.uuid4().hex[:12] + ".png"
    out = os.path.join(OUT, name)
    build_cover.make_cover(req.coverSpec, out, size=(req.width, req.height))
    return {"cover": f"/file/{name}"}

@app.get("/job/{job_id}")
def job(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="no such job")
    return {"jobId": job_id, **JOBS[job_id]}

@app.get("/file/{name}")
def get_file(name: str):
    p = os.path.join(OUT, os.path.basename(name))
    if not os.path.isfile(p):
        raise HTTPException(status_code=404, detail="not found")
    mt = "image/png" if name.lower().endswith(".png") else "video/mp4"
    return FileResponse(p, media_type=mt, filename=name)
