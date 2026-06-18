FROM python:3.12-slim

# ffmpeg + 日本語フォント(Noto Sans JP / CJK)。chromiumの依存は playwright install --with-deps が入れる
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg fonts-noto-cjk fonts-noto-color-emoji ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps chromium

# アプリ本体 ＋ 実データCSV（当面は同梱。運用では定期更新を推奨）
COPY build_data.py build_reel.py render_reel.py build_cover.py research.py worker.py ./
COPY sp500_datahub.csv fx.csv ./

ENV OUT_DIR=/tmp/out
# 任意: fal.ai のカバー背景生成に使用（未設定ならkintsugi調フォールバック）
ENV FAL_KEY=""
# Claude API（②a リサーチに使用）
ENV ANTHROPIC_KEY=""
EXPOSE 8080
CMD uvicorn worker:app --host 0.0.0.0 --port ${PORT:-8080}
