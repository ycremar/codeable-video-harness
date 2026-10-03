# Portability recipe; not claimed executed in the original cloud run.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /work
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python scripts/prepare_fonts.py
ENTRYPOINT ["python", "-m", "vch"]
CMD ["validate", "examples/explainer.json"]
