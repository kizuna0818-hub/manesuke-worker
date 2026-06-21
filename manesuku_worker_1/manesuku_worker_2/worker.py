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
import os, uuid, threading, traceback, urllib.request
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
    introUrl: Optional[str] = None   # カバー/ポスターを頭に付ける場合
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

def _produce(job_id, spec, intro_url, fps):
    try:
        html = build_reel.build(spec)
        hpath = os.path.join(OUT, f"{job_id}.html"); open(hpath, "w").write(html)
        reel = os.path.join(OUT, f"{job_id}_reel.mp4")
        render_reel.render_html_to_mp4(hpath, reel, fps=fps)
        final = os.path.join(OUT, f"{job_id}.mp4")
        if intro_url:
            intro_img = os.path.join(OUT, f"{job_id}_intro.png")
            urllib.request.urlretrieve(intro_url, intro_img)
            intro_clip = os.path.join(OUT, f"{job_id}_intro.mp4")
            render_reel.image_to_clip(intro_img, intro_clip, dur=3.5, fps=fps)
            render_reel.concat_mp4s([intro_clip, reel], final, fps=fps)
        else:
            os.replace(reel, final)
        JOBS[job_id] = {"status": "done", "mp4": f"/file/{job_id}.mp4"}
    except Exception as e:
        JOBS[job_id] = {"status": "error", "error": str(e), "trace": traceback.format_exc()[-1000:]}

@app.post("/produce")
def produce(req: ProduceReq):
    """spec -> 完成MP4（非同期）。jobIdを返すのでポーリング。"""
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"status": "processing"}
    threading.Thread(target=_produce, args=(job_id, req.spec, req.introUrl, req.fps), daemon=True).start()
    return {"jobId": job_id, "status": "processing"}

class CoverReq(BaseModel):
    coverSpec: dict
    bgPrompt: Optional[str] = None
    width: int = 1080
    height: int = 1350

@app.post("/cover")
def cover_ep(req: CoverReq):
    """カバー生成: AI背景(fal.ai/FAL_KEY) ＋ 実数HTMLオーバーレイ → PNG"""
    name = uuid.uuid4().hex[:12] + ".png"
    out = os.path.join(OUT, name)
    build_cover.make_cover(req.coverSpec, out, bg_prompt=req.bgPrompt, size=(req.width, req.height))
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
