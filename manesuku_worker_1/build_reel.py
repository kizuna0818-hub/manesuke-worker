#!/usr/bin/env python3
"""
build_reel.py — マネスク Reel 汎用ビルダー
Spec(dict) を渡すと、決定論レンダリング対応の縦型(1080x1920)アニメHTMLを生成する。
今回のテスラ制作テンプレ(kintsugi: ink/cream/gold)を一般化したもの。

  from build_reel import build
  open("reel.html","w").write(build(spec))

ビートtype: hook / setup / chart / highlight / stat / lesson / cta
Spec の最小例は __main__(tesla) を参照。
"""
import json

def fmt(v, cur):
    v = round(v)
    if cur == "yen": return "¥" + f"{v:,}"
    if cur == "usd": return "$" + f"{v:,}"
    return f"{v:,}"

def counter_font_u(series, cur, cap=8.6):
    glyphs = max(len(fmt(x, cur)) for x in series)
    return round(min(cap, 46.0 / (0.6 * max(glyphs, 1))), 2)

CSS = r'''
  :root{--ink:#0B0B0F;--ink2:#15120C;--cream:#F2EBDD;--cream-dim:#9A9484;--gold:#E2B45C;--gold-soft:#F3D79A;--red:#E27A5C;--line:#2A2620;
    --jp:"Noto Sans JP",system-ui,sans-serif;--mono:"Roboto Mono",ui-monospace,monospace;}
  *{margin:0;padding:0;box-sizing:border-box}
  html,body{height:100%;background:#000;display:flex;align-items:center;justify-content:center;overflow:hidden;font-family:var(--jp)}
  .stage{position:relative;height:min(100vh,calc(100vw*16/9));width:calc(min(100vh,calc(100vw*16/9))*9/16);
    background:radial-gradient(120% 80% at 50% 18%,var(--ink2) 0%,var(--ink) 55%);overflow:hidden;color:var(--cream);--u:calc(min(100vh,calc(100vw*16/9))/100);}
  .glow{position:absolute;inset:0;background:radial-gradient(60% 35% at 50% 30%,rgba(226,180,92,.10),transparent 70%);animation:breathe 7s ease-in-out infinite}
  @keyframes breathe{0%,100%{opacity:.55}50%{opacity:.9}}
  .prog{position:absolute;top:0;left:0;height:calc(var(--u)*0.5);width:0%;background:linear-gradient(90deg,var(--gold),var(--gold-soft));z-index:9}
  .beat{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:0 calc(var(--u)*5);opacity:0;pointer-events:none}
  .eyebrow{font-size:calc(var(--u)*2.6);letter-spacing:.28em;color:var(--gold);font-weight:700;margin-bottom:calc(var(--u)*3)}
  .big{font-weight:900;line-height:1.16;font-size:calc(var(--u)*6.4);letter-spacing:.01em}
  .sub{font-size:calc(var(--u)*3);color:var(--cream-dim);font-weight:500;margin-top:calc(var(--u)*3.5);line-height:1.5}
  .stat{font-family:var(--mono);font-weight:700;color:var(--gold);white-space:nowrap;font-size:calc(var(--u)*16);line-height:1}
  .cbeat{justify-content:flex-start;padding-top:calc(var(--u)*12)}
  .clabel{font-size:calc(var(--u)*3.2);color:var(--cream);font-weight:700;letter-spacing:.02em}
  .cval{font-family:var(--mono);font-weight:700;font-variant-numeric:tabular-nums;white-space:nowrap;margin-top:calc(var(--u)*1.5);text-shadow:0 0 calc(var(--u)*4) rgba(226,180,92,.30)}
  .cyear{font-family:var(--mono);font-weight:700;color:var(--cream);font-size:calc(var(--u)*3);margin-top:calc(var(--u)*0.5);opacity:.7}
  .chart{position:relative;width:100%;height:calc(var(--u)*44);margin-top:calc(var(--u)*4)}
  .chart svg{width:100%;height:100%;display:block}
  .gridline{stroke:var(--line);stroke-width:.4;vector-effect:non-scaling-stroke}
  .pl{fill:none;stroke-width:2.8;vector-effect:non-scaling-stroke;stroke-linejoin:round}
  .refl{fill:none;stroke:var(--cream-dim);stroke-width:2;stroke-dasharray:4 4;vector-effect:non-scaling-stroke;opacity:.6}
  .dot{position:absolute;width:calc(var(--u)*2.6);height:calc(var(--u)*2.6);border-radius:50%;transform:translate(-50%,-50%);left:0;top:100%}
  .xlab{position:absolute;bottom:calc(var(--u)*-4.5);font-size:calc(var(--u)*1.9);color:var(--cream-dim);transform:translateX(-50%)}
  .legend{display:flex;gap:calc(var(--u)*5);margin-top:calc(var(--u)*8);font-size:calc(var(--u)*2.3);color:var(--cream-dim)}
  .legend i{display:inline-block;width:calc(var(--u)*4);height:calc(var(--u)*0.8);margin-right:calc(var(--u)*1.5);vertical-align:middle;border-radius:2px}
  .pop{position:absolute;transform:translate(-50%,0);width:calc(var(--u)*23);text-align:left;background:rgba(13,12,16,.94);border:1px solid var(--line);
    border-radius:calc(var(--u)*1.8);padding:calc(var(--u)*1.5) calc(var(--u)*2);box-shadow:0 calc(var(--u)*1) calc(var(--u)*4) rgba(0,0,0,.55);opacity:0;z-index:6}
  .pop b{display:block;font-size:calc(var(--u)*2.15);font-weight:900;line-height:1.3;color:var(--cream)}
  .pop .ps{display:block;font-size:calc(var(--u)*1.7);color:var(--cream-dim);margin-top:calc(var(--u)*0.5)}
  .pop .arr{font-size:calc(var(--u)*2);font-weight:900;margin-right:calc(var(--u)*0.6)}
  .pop.up{border-color:rgba(226,180,92,.55)} .pop.up .arr{color:var(--gold)}
  .pop.down{border-color:rgba(226,122,92,.55)} .pop.down .arr{color:var(--red)}
  .pillred{display:inline-block;border:1px solid var(--red);color:var(--red);border-radius:999px;padding:calc(var(--u)*1.4) calc(var(--u)*4);font-size:calc(var(--u)*2.8);font-weight:700;margin-bottom:calc(var(--u)*4)}
  .cta .big{color:var(--cream)} .cta .handle{color:var(--gold);font-weight:900;margin-top:calc(var(--u)*2.5);font-size:calc(var(--u)*4.4)}
  .endnote{margin-top:calc(var(--u)*7);font-size:calc(var(--u)*1.7);color:var(--cream-dim);line-height:1.55;max-width:84%}
  .control{position:absolute;inset:0;z-index:20;display:flex;align-items:center;justify-content:center;background:rgba(7,7,10,.55);cursor:pointer;transition:opacity .3s}
  .control.hide{opacity:0;pointer-events:none}
  .play{width:calc(var(--u)*18);height:calc(var(--u)*18);border-radius:50%;border:2px solid var(--gold);display:flex;align-items:center;justify-content:center;color:var(--gold);background:rgba(0,0,0,.35)}
  .play svg{width:42%;height:42%;margin-left:8%}
  .replay{position:absolute;top:calc(var(--u)*3);right:calc(var(--u)*4);z-index:21;border:1px solid var(--line);color:var(--cream-dim);background:rgba(0,0,0,.3);border-radius:999px;padding:calc(var(--u)*1.2) calc(var(--u)*3);font-family:var(--jp);font-size:calc(var(--u)*2);cursor:pointer;opacity:0;transition:.3s}
  .replay.show{opacity:1}
'''
COLOR = {"cream":"var(--cream)","gold":"var(--gold)","red":"var(--red)"}

def beat_html(b, i, charts):
    bid = f"beat{i}"; t = b["type"]
    if t == "hook":
        return bid, f'<div class="beat" id="{bid}"><div class="eyebrow">{b.get("eyebrow","")}</div><div class="big">{b["big"]}</div></div>'
    if t == "setup":
        eb = f'<div class="eyebrow">{b["eyebrow"]}</div>' if b.get("eyebrow") else ""
        sub = f'<div class="sub">{b["sub"]}</div>' if b.get("sub") else ""
        return bid, f'<div class="beat" id="{bid}">{eb}<div class="big">{b["big"]}</div>{sub}</div>'
    if t == "highlight":
        pill = f'<div class="pillred">{b["pill"]}</div>' if b.get("pill") else ""
        sub = f'<div class="sub">{b["sub"]}</div>' if b.get("sub") else ""
        return bid, f'<div class="beat" id="{bid}">{pill}<div class="big">{b["big"]}</div>{sub}</div>'
    if t == "stat":
        sub = f'<div class="sub" style="font-size:calc(var(--u)*3.4)">{b["sub"]}</div>' if b.get("sub") else ""
        return bid, f'<div class="beat" id="{bid}"><div class="stat">{b["big"]}</div>{sub}</div>'
    if t == "lesson":
        return bid, f'<div class="beat" id="{bid}"><div class="big">{b["big"]}</div></div>'
    if t == "cta":
        return bid, (f'<div class="beat cta" id="{bid}"><div class="big">{b["big"]}</div>'
                     f'<div class="handle">{b.get("handle","")}</div>'
                     f'<div class="endnote">{b.get("endnote","")}</div></div>')
    if t == "chart":
        cur = b.get("currency","yen"); c = charts[b["id"]]
        col = COLOR.get(b.get("lineColor","gold"),"var(--gold)")
        ccol = COLOR.get(b.get("counterColor", "gold" if cur=="yen" else "cream"),"var(--gold)")
        pops=""
        for j,p in enumerate(b.get("popups",[])):
            pid=f"{b['id']}_pop{j}"; up=p.get("up",True); dr="up" if up else "down"; ar="▲" if up else "▼"
            pops+=f'<div class="pop {dr}" id="{pid}" style="left:{p["left"]}%;top:{p["top"]}%"><span class="arr">{ar}</span><b>{p["title"]}</b><span class="ps">{p.get("sub","")}</span></div>'
        has_area=b.get("area",True)
        gstop = "#E2B45C" if b.get("lineColor")=="gold" else "#F2EBDD"
        grad = f'<linearGradient id="g_{b["id"]}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{gstop}" stop-opacity=".40"/><stop offset="1" stop-color="{gstop}" stop-opacity="0"/></linearGradient>' if has_area else ""
        area = f'<path id="area_{b["id"]}" fill="url(#g_{b["id"]})"></path>' if has_area else ""
        ref = ""
        if b.get("ref"):
            ref = (f'<path id="refp_{b["id"]}" class="refl"></path>' if b["ref"].get("type")=="series"
                   else f'<line id="ref_{b["id"]}" class="refl"></line>')
        xl="".join(f'<span class="xlab" style="left:{xx[1]}%">{xx[0]}</span>' for xx in b.get("xlabels",[]))
        leg=""
        if b.get("legend"):
            leg="".join(f'<span><i style="background:{COLOR.get(lg["color"],"var(--gold)")}"></i>{lg["label"]}</span>' for lg in b["legend"])
            leg=f'<div class="legend">{leg}</div>'
        svg=(f'<svg viewBox="0 0 100 60" preserveAspectRatio="none"><defs>{grad}'
             f'<clipPath id="clip_{b["id"]}"><rect id="rect_{b["id"]}" x="-2" y="-5" width="0" height="70"/></clipPath></defs>'
             f'<line class="gridline" x1="0" y1="59.6" x2="100" y2="59.6"/>'
             f'<g clip-path="url(#clip_{b["id"]})">{area}{ref}<path id="line_{b["id"]}" class="pl" style="stroke:{col}"></path></g></svg>')
        return bid, (f'<div class="beat cbeat" id="{bid}"><div class="clabel">{b["label"]}</div>'
                     f'<div class="cval" id="cv_{b["id"]}" style="color:{ccol};font-size:calc(var(--u)*{c["fu"]})">{fmt(c["series"][0],cur)}</div>'
                     f'<div class="cyear" id="cy_{b["id"]}">{c["yr"][0]}年</div>'
                     f'<div class="chart" id="chart_{b["id"]}">{svg}<div class="dot" id="dot_{b["id"]}" style="background:{col};box-shadow:0 0 calc(var(--u)*3) {col}"></div>{pops}{xl}</div>{leg}</div>')
    raise ValueError("unknown beat type "+t)

def build(spec):
    data=spec["data"]; yr=data["yr"]; series=data["series"]
    beats=[]; t0=0.0; charts={}
    for i,b in enumerate(spec["beats"]):
        dur=float(b["dur"]); s=t0; e=t0+dur; t0=e; beats.append((i,b,s,e))
        if b["type"]=="chart":
            cur=b.get("currency","yen"); ser=series[b["series"]]
            draw=float(b.get("draw", min(dur-2.0, dur*0.55)))
            charts[b["id"]]={"series":ser,"yr":yr,"cur":cur,"start":s,"draw":draw,"fu":counter_font_u(ser,cur),"ref":b.get("ref"),"popups":[]}
            for j,p in enumerate(b.get("popups",[])):
                ps=s+float(p["at"])*draw; pe=ps+float(p.get("hold",2.7))
                charts[b["id"]]["popups"].append([f"{b['id']}_pop{j}",round(ps,2),round(pe,2)])
    DUR=round(t0,2)
    body=[]; cfg_beats=[]
    for (i,b,s,e) in beats:
        bid,h=beat_html(b,i,charts); body.append(h)
        cfg_beats.append({"id":bid,"s":round(s,2),"e":round(e,2),"chart":b.get("id") if b["type"]=="chart" else None})
    cfg={"dur":DUR,"beats":cfg_beats,
         "charts":{k:{"start":round(v["start"],2),"draw":round(v["draw"],2),"cur":v["cur"],"ref":v["ref"],"pops":v["popups"]} for k,v in charts.items()},
         "data":{"yr":yr,"series":series}}
    cfgjson=json.dumps(cfg,separators=(',',':'),ensure_ascii=False)
    html=f'''<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{spec.get("title","Reel")}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&family=Roboto+Mono:wght@500;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head>
<body><div class="stage" id="stage"><div class="glow"></div><div class="prog" id="prog"></div>
{chr(10).join(body)}
  <div class="control" id="control"><div class="play"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg></div></div>
  <button class="replay" id="replay">&#8635; もう一度</button>
</div>
<script>
const CFG={cfgjson};window.CFG=CFG;
const el=id=>document.getElementById(id);
const yen=n=>"¥"+Math.round(n).toLocaleString('en-US'), usd=n=>"$"+Math.round(n).toLocaleString('en-US');
const FMT=(v,c)=>c==='usd'?usd(v):c==='yen'?yen(v):Math.round(v).toLocaleString('en-US');
function build(){{
  for(const k in CFG.charts){{const c=CFG.charts[k];const ser=CFG.data.series[k];const N=ser.length;
    const yMax=Math.max.apply(null,ser)*1.08, X=i=>i/(N-1)*100, Y=v=>60-(v/yMax)*52-2;
    const P=a=>{{let d="M0 "+Y(a[0]).toFixed(2);for(let i=1;i<N;i++)d+=" L"+X(i).toFixed(2)+" "+Y(a[i]).toFixed(2);return d;}};
    el('line_'+k).setAttribute('d',P(ser));
    if(el('area_'+k))el('area_'+k).setAttribute('d',P(ser)+" L100 60 L0 60 Z");
    if(c.ref){{
      if(c.ref.type==='series'&&el('refp_'+k)){{el('refp_'+k).setAttribute('d',P(CFG.data.series[c.ref.series]));}}
      else if(el('ref_'+k)){{const L=el('ref_'+k);const ry=Y(c.ref.value).toFixed(2);
        L.setAttribute('x1',0);L.setAttribute('x2',100);L.setAttribute('y1',ry);L.setAttribute('y2',ry);}}
    }}
    c._N=N;c._Y=Y;c._X=X;}}
}}
function drawChart(k,cp){{const c=CFG.charts[k];const ser=CFG.data.series[k];const N=c._N;
  el('rect_'+k).setAttribute('width',(cp*104).toFixed(2));
  const i=Math.min(N-1,Math.round(cp*(N-1)));
  el('cv_'+k).textContent=FMT(ser[i],c.cur);el('cy_'+k).textContent=CFG.data.yr[i]+"年";
  el('dot_'+k).style.left=c._X(i)+"%";el('dot_'+k).style.top=(c._Y(ser[i])/60*100)+"%";}}
function fade(t,s,e){{return Math.max(0,Math.min(1,(t-s)/0.35,(e-t)/0.35));}}
window.renderAt=function(t){{
  el('prog').style.width=Math.min(100,(t/CFG.dur)*100)+'%';
  let ai=0;for(let i=0;i<CFG.beats.length;i++){{if(t>=CFG.beats[i].s&&t<CFG.beats[i].e)ai=i;}}
  if(t>=CFG.dur)ai=CFG.beats.length-1;
  for(let i=0;i<CFG.beats.length;i++)el(CFG.beats[i].id).style.opacity='0';
  const a=CFG.beats[ai];const k=Math.min(1,(t-a.s)/0.5);el(a.id).style.opacity=String(k);
  if(ai>0&&k<1)el(CFG.beats[ai-1].id).style.opacity=String(1-k);
  for(const ck in CFG.charts){{const c=CFG.charts[ck];drawChart(ck,t>=c.start?Math.min(1,(t-c.start)/c.draw):0);}}
  for(const ck in CFG.charts){{const c=CFG.charts[ck];const active=(a.chart===ck);
    for(const pw of c.pops)el(pw[0]).style.opacity=active?String(fade(t,pw[1],pw[2])):'0';}}
}};
let startT=null,raf=null;
function frame(now){{if(startT===null)startT=now;const t=(now-startT)/1000;window.renderAt(t);
  if(t<CFG.dur)raf=requestAnimationFrame(frame);else el('replay').classList.add('show');}}
function play(){{el('control').classList.add('hide');startT=null;el('replay').classList.remove('show');cancelAnimationFrame(raf);raf=requestAnimationFrame(frame);}}
build();window.renderAt(0);
el('control').addEventListener('click',play);el('replay').addEventListener('click',play);
</script></body></html>'''
    return html

if __name__=="__main__":
    d=json.load(open('tesla_series.json'))
    spec={
      "title":"Reel JP — Tesla 7y",
      "data":{"yr":d["yr"],"series":{"price":d["price"],"val":d["val"]}},
      "beats":[
        {"type":"setup","dur":4.5,"eyebrow":"2019年6月","big":"テスラに<br>100万円投資💸","sub":"1株 約 $15"},
        {"type":"chart","dur":16,"id":"price","label":"テスラ株価（米ドル）","series":"price","currency":"usd",
         "lineColor":"cream","draw":13,"xlabels":[["2019",0],["2022",50],["2026",100]],
         "popups":[
           {"at":0.179,"left":24,"top":26,"up":True,"title":"2020年に +743%","sub":"S&P500入り・EV急増"},
           {"at":0.345,"left":39,"top":4,"up":True,"title":"時価総額 1兆ドル超え","sub":"ハーツが10万台発注"},
           {"at":0.50,"left":50,"top":50,"up":False,"title":"利上げ＋Twitter買収","sub":"マスク氏が株を売却"},
           {"at":0.774,"left":69,"top":4,"up":True,"title":"トランプ氏 勝利","sub":"自動運転に追い風"},
           {"at":0.929,"left":73,"top":18,"up":True,"title":"ロボタクシー進展","sub":"史上最高値 $490"}]},
        {"type":"chart","dur":13,"id":"val","label":"あなたの資産（円）","series":"val","currency":"yen",
         "lineColor":"gold","draw":7,"ref":{"type":"flat","value":d["invest"]},
         "xlabels":[["2019",0],["2022",50],["2026",100]],
         "legend":[{"color":"gold","label":"評価額"},{"color":"cream","label":"投資額（100万）"}]},
        {"type":"highlight","dur":4,"pill":"2022年株価大暴落","big":"−65%","sub":"ここで恐れない！<br>握る！"},
        {"type":"stat","dur":4,"big":"40x","sub":"100万円 → 約4,000万円"},
        {"type":"lesson","dur":3.5,"big":"早く始めて、<br>握る。"},
        {"type":"cta","dur":5.5,"big":"コツコツ投資。<br>今からでも。","handle":"マネスク → @Money_school1515",
         "endnote":"※情報提供であり投資助言ではありません。個別株は値動きが大きく、損失の可能性があります。過去の実績は将来を保証しません。"}
      ]
    }
    open("reel.html","w").write(build(spec))
    print("OK reel.html  duration=", sum(b["dur"] for b in spec["beats"]))
