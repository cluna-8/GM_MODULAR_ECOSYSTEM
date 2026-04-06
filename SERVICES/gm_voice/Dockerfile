FROM python:3.11-slim

# ffmpeg: requerido por faster-whisper para decodificar audio
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 7003

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7003"]
