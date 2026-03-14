FROM python:3.11-slim

WORKDIR /app

# Dépendances système
RUN apt-get update && apt-get install -y \
    libpq-dev gcc wget tar libespeak-ng1 \
    && rm -rf /var/lib/apt/lists/*

# Installer Piper TTS — garder tout le dossier (libs incluses)
RUN wget -q https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz \
       -O /tmp/piper.tar.gz \
    && tar -xzf /tmp/piper.tar.gz -C /opt \
    && rm /tmp/piper.tar.gz \
    && ln -s /opt/piper/piper /usr/local/bin/piper

# Télécharger la voix française
RUN mkdir -p /app/piper_models \
    && wget -q "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx" \
       -O /app/piper_models/fr_FR-siwis-medium.onnx \
    && wget -q "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx.json" \
       -O /app/piper_models/fr_FR-siwis-medium.onnx.json

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Supprimer le .env du container (les vars sont définies par Railway/Dockerfile ENV)
RUN rm -f .env

ENV PIPER_PATH=piper
ENV PIPER_MODEL=/app/piper_models/fr_FR-siwis-medium.onnx

CMD gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
