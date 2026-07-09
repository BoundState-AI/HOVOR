# HOVOR! backend + web client — deployed on Railway, reverse-proxied from
# boundstate.ai/hovor (see landing repo vercel.json). Same pattern as bouncer.
FROM python:3.12-slim

WORKDIR /srv
COPY backend/ ./

RUN pip install --no-cache-dir ".[realtime]"

ENV HOST=0.0.0.0
ENV PORT=8080
ENV PUBLIC_BASE_PATH=/hovor

CMD ["sh", "-c", "uvicorn hovor.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8080}"]
