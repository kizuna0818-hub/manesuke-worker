#!/usr/bin/env python3
"""
build_data.py — マネスク Reel データモジュール（②）
scenario(銘柄・期間・金額) → 実データ取得＋計算 → Specの data ブロックを返す。

設計の肝: 数字はここ（コード）でしか作らない。LLMには計算させない。
返り値 data = {yr, series{...}, headline{...}, meta{...}, popups:[]}

対応シナリオ:
  - {"type":"dca_index", "index":"sp500", "monthly":1500, "start":"2014-01", "end":"2026-05"}
  - {"type":"lump_single","asset":"TSLA","amount":1000000,"entryDate":"2019-06",
     "anchors":{"2019-06":14.90,...,"2026-06":404.66}}   # 分割調整後の実価格(転換点)
データが取れない/最新の壁に当たったら ValueError("needsReview: ...") を投げる(捏造しない)。
"""
import pandas as pd, json, calendar

# ---------- 為替（実数・月次平均） ----------
def fx_monthly(country="Japan"):
    fx = pd.read_csv("fx.csv")
    fx = fx[fx["Country"].str.lower() == country.lower()].copy()
    fx["Date"] = pd.to_datetime(fx["Date"])
    fx["r"] = pd.to_numeric(fx["Exchange rate"], errors="coerce")
    s = fx.dropna(subset=["r"]).groupby(fx["Date"].dt.to_period("M"))["r"].mean()
    if s.empty: raise ValueError("needsReview: FX系列が空")
    return s  # index=Period('M'), value=rate

# ---------- 指数（実数・月次） ----------
def sp500_monthly():
    df = pd.read_csv("sp500_datahub.csv")[["Date", "SP500"]].dropna()
    df["Date"] = pd.to_datetime(df["Date"])
    return pd.Series(df["SP500"].values, index=df["Date"].dt.to_period("M"))

INDEX = {"sp500": sp500_monthly}

# ---------- ① 指数つみたて（DCA・円建て） ----------
def dca_index(sc):
    amount = float(sc["monthly"]); idx = INDEX[sc["index"]]()
    fx = fx_monthly(sc.get("fx_country", "Japan"))
    start = pd.Period(sc["start"], "M"); end = pd.Period(sc.get("end", str(idx.index.max())), "M")
    months = pd.period_range(start, end, freq="M")
    units = 0.0; contrib = 0.0; val=[]; con=[]; yr=[]
    for m in months:
        if m not in idx.index or m not in fx.index:
            raise ValueError(f"needsReview: {m} の指数/為替が無い（最新の壁の可能性）")
        p = float(idx[m]); f = float(fx[m])
        units += (amount / f) / p                # 円→ドル→指数ユニット
        contrib += amount
        val.append(round(units * p * f))         # 評価額(円)
        con.append(round(contrib)); yr.append(m.year)
    final = val[-1]
    head = {"invested": round(contrib), "final": final, "mult": round(final/contrib, 2),
            "months": len(months), "indexStart": round(float(idx[start]),2), "indexEnd": round(float(idx[end]),2)}
    return {"yr": yr, "series": {"val": val, "contrib": con}, "headline": head,
            "meta": {"type":"dca_index","index":sc["index"],"monthly":amount,
                     "fxStart":round(float(fx[start]),2),"fxEnd":round(float(fx[end]),2)}, "popups": []}

# ---------- ② 個別株 一括（実アンカー→月次補間） ----------
def lump_single(sc):
    amount = float(sc["amount"]); fx = fx_monthly(sc.get("fx_country", "Japan"))
    anchors = {pd.Period(k, "M"): float(v) for k, v in sc["anchors"].items()}
    months = pd.period_range(min(anchors), max(anchors), freq="M")
    price = pd.Series(anchors).reindex(months).interpolate(method="linear")
    entry = pd.Period(sc["entryDate"], "M")
    if entry not in fx.index: raise ValueError(f"needsReview: 購入月 {entry} の為替が無い")
    p0 = float(price[entry]); f0 = float(fx[entry])
    val=[]; pr=[]; yr=[]
    for m in months:
        f = float(fx[m]) if m in fx.index else float(fx.iloc[-1])
        pr.append(round(float(price[m]), 2))
        val.append(round(amount * (price[m]/p0) * (f/f0)))
        yr.append(m.year)
    final = val[-1]; trough = min(val)
    head = {"entryP": round(p0,2), "nowP": pr[-1], "fxIn": round(f0,1),
            "fxNow": round(float(fx.iloc[-1]),1), "amount": round(amount),
            "final": final, "mult": round(final/amount, 2),
            "trough": (trough if trough < amount else None)}
    return {"yr": yr, "series": {"price": pr, "val": val}, "headline": head,
            "meta": {"type":"lump_single","asset":sc["asset"],"entryDate":sc["entryDate"]}, "popups": []}

# ---------- 個別株の年次データ（VPSではrequestsで取得・ここは雛形） ----------
def macrotrends_annual(ticker):
    """best-effort: 分割調整後の年次 高/安/終値。失敗時 None。
    ※サンドボックスは macrotrends.net 非許可のため未検証。VPS(requests)では動作。"""
    try:
        import requests, re
        url=f"https://www.macrotrends.net/stocks/charts/{ticker}/x/stock-price-history"
        html=requests.get(url, timeout=15, headers={"User-Agent":"Mozilla/5.0"}).text
        rows=re.findall(r"\|\s*(\d{4})\s*\|[^|]*\|[^|]*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|", html)
        out={int(y):{"high":float(h),"low":float(l),"close":float(c)} for y,_,h,l,c in rows}
        return out or None
    except Exception:
        return None

# ---------- ディスパッチ ----------
def build_data(sc):
    t = sc.get("type")
    if t == "dca_index":   return dca_index(sc)
    if t == "lump_single": return lump_single(sc)
    raise ValueError("unknown scenario type: %r" % t)

# ---------- 自己テスト ----------
if __name__ == "__main__":
    # A) Tesla 一括（既存 tesla_series.json を再現できるか）
    tsla = build_data({"type":"lump_single","asset":"TSLA","amount":1_000_000,"entryDate":"2019-06",
        "anchors":{"2019-06":14.90,"2019-12":27.89,"2020-03":30.00,"2020-12":235.22,"2021-11":410.00,
                   "2022-01":360.00,"2022-12":123.18,"2023-06":261.00,"2023-12":248.48,"2024-04":142.05,
                   "2024-10":250.00,"2024-12":430.00,"2025-04":222.00,"2025-08":330.00,"2025-12":480.00,"2026-06":404.66}})
    print("TSLA lump  final=¥{:,}  mult={}x  trough={}  ".format(
        tsla["headline"]["final"], tsla["headline"]["mult"], tsla["headline"]["trough"]))

    # B) スタバ DCA（¥1,500/月を S&P500 へ 2014-01〜2026-05）
    sb = build_data({"type":"dca_index","index":"sp500","monthly":1500,"start":"2014-01","end":"2026-05"})
    h=sb["headline"]
    print("Starbucks DCA  invested=¥{:,}  final=¥{:,}  mult={}x  months={}".format(
        h["invested"], h["final"], h["mult"], h["months"]))
