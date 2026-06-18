#!/usr/bin/env python3
"""
research.py — 個別株リサーチ（②a）
Claude API（サーバ側 web_search）で、分割調整後の株価アンカー＋出来事＋出典を取得。
これは「②a」の自動化＝今まで手作業でMacroTrendsを見て決めていた部分。

  from research import research_single_stock
  r = research_single_stock("NFLX", "2019-12")   # 要 ANTHROPIC_KEY
  # -> {"anchors":{"YYYY-MM":price,...}, "currentPrice":num, "popups":[{...,"src":...}]}

ガードレール:
- 出典(src)の無い出来事・推測値は採用しない（プロンプトで厳命＋検証）。
- JSONが壊れている/アンカー不足なら ValueError("needsReview: ...") を投げて止める。
※数字の最終確定は build_data（②）が実データCSV＋このアンカーで行う。LLMには計算させない。
"""
import os, re, json, requests

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

PROMPT = """あなたは金融データのリサーチャです。web検索を使って事実を確認してください。
対象: {asset} の価格。期間: {entry} 〜 2026-06（現在）。
({asset} は米国株・ETF・暗号資産(BTC等)のいずれか。ティッカー/通貨記号で判断してください）

次を**実数**で集めてください（基準を統一: 株式/ETFは split/配当 調整後、暗号資産は USD 現物価格）:
1) 転換点の価格アンカー（各年＋大きく動いた主要月）。最低でも {entry} と 2026-06 を含む。
2) 現在(2026-06)の価格。
3) 大きく動いた局面 3〜6件。各々に理由と**出典URL**。

出力は**JSONのみ**（前置き・コードフェンス・説明文なし）:
{{"anchors":{{"YYYY-MM":number,...}},"currentPrice":number,
  "popups":[{{"date":"YYYY-MM","up":true,"title":"...(日本語/12字以内)","sub":"...(日本語/16字以内)","src":"https://..."}}]}}

厳守:
- 出典が確認できない数値・出来事は**出さない**。推測値・概算の捏造は禁止。
- すべて同じ基準で揃える（株式/ETFは調整後で一貫、暗号資産はUSD現物）。"""

def _extract_json(content_blocks):
    """Anthropicレスポンス(複数ブロック)からテキストを集めてJSONを取り出す。"""
    texts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
    blob = "\n".join(texts).strip()
    blob = re.sub(r"^```(json)?|```$", "", blob.strip(), flags=re.MULTILINE).strip()
    m = re.search(r"\{.*\}", blob, re.DOTALL)   # 最初の{...}を拾う
    if not m:
        raise ValueError("needsReview: リサーチ結果からJSONを抽出できず")
    return json.loads(m.group(0))

def research_single_stock(asset, entry_date, api_key=None, model="claude-sonnet-4-6"):
    api_key = api_key or os.environ.get("ANTHROPIC_KEY")
    if not api_key:
        raise ValueError("needsReview: ANTHROPIC_KEY 未設定")
    body = {
        "model": model, "max_tokens": 2000,
        "messages": [{"role": "user", "content": PROMPT.format(asset=asset, entry=entry_date)}],
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}],
    }
    r = requests.post(ANTHROPIC_URL, timeout=120, json=body, headers={
        "x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    if r.status_code != 200:
        raise ValueError(f"needsReview: Anthropic {r.status_code}: {r.text[:200]}")
    data = _extract_json(r.json().get("content", []))

    # 検証: 必須アンカー・出典
    anchors = data.get("anchors", {})
    if entry_date not in anchors:
        raise ValueError(f"needsReview: アンカーに購入月 {entry_date} が無い")
    if "currentPrice" in data:
        anchors["2026-06"] = data["currentPrice"]
    if "2026-06" not in anchors:
        raise ValueError("needsReview: 現在(2026-06)の株価が無い")
    pops = [p for p in data.get("popups", []) if p.get("src", "").startswith("http")]
    if data.get("popups") and not pops:
        raise ValueError("needsReview: 出典付きの出来事が1件も無い")
    return {"anchors": {k: float(v) for k, v in anchors.items()},
            "currentPrice": float(anchors["2026-06"]), "popups": pops}

if __name__ == "__main__":
    import sys
    a = sys.argv[1] if len(sys.argv) > 1 else "NFLX"
    e = sys.argv[2] if len(sys.argv) > 2 else "2019-12"
    print(json.dumps(research_single_stock(a, e), ensure_ascii=False, indent=2))
