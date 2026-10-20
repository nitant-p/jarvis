FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm install --global npm@11.21.1 && npm ci
COPY frontend/ ./
RUN npm run build

FROM debian:bookworm-slim AS inference
RUN apt-get update && apt-get install -y --no-install-recommends git cmake g++ make ca-certificates libcurl4-openssl-dev && rm -rf /var/lib/apt/lists/*
# Verified upstream revisions, matching the native runtimes used in local evaluation.
ARG LLAMA_REV=620d2225cc436ab0b001e3200e590e3b286ef9ab
ARG WHISPER_REV=d2a764c648779feb36d44363f212a29b00aad1af
RUN git init /src/whisper && git -C /src/whisper remote add origin https://github.com/ggml-org/whisper.cpp.git && git -C /src/whisper fetch --depth=1 origin "$WHISPER_REV" && git -C /src/whisper checkout FETCH_HEAD
RUN cmake -S /src/whisper -B /build/whisper -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=OFF -DGGML_OPENMP=OFF -DWHISPER_BUILD_TESTS=OFF && cmake --build /build/whisper --target whisper-cli -j2
RUN git init /src/llama && git -C /src/llama remote add origin https://github.com/ggml-org/llama.cpp.git && git -C /src/llama fetch --depth=1 origin "$LLAMA_REV" && git -C /src/llama checkout FETCH_HEAD
RUN cmake -S /src/llama -B /build/llama -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=OFF -DGGML_OPENMP=OFF -DLLAMA_CURL=OFF -DLLAMA_OPENSSL=OFF && cmake --build /build/llama --target llama-server -j2

FROM python:3.12-slim-bookworm AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libgomp1 libcurl4 ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY --from=inference /build/whisper/bin/whisper-cli /usr/local/bin/whisper-cli
COPY --from=inference /build/llama/bin/llama-server /usr/local/bin/llama-server
COPY pyproject.toml alembic.ini ./
COPY backend/ backend/
RUN pip install --no-deps . && useradd --uid 10001 --create-home jarvis && mkdir -p /app/data/audio && chown -R jarvis:jarvis /app/data
COPY --from=web /web/dist /app/web
ENV JARVIS_DATA_DIR=/app/data PYTHONUNBUFFERED=1
USER jarvis
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1
CMD ["python", "-m", "uvicorn", "jarvis.api:app", "--host", "0.0.0.0", "--port", "8000"]
