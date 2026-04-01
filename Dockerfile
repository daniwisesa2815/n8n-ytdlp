FROM python:3.11-slim
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app.py .
EXPOSE 10000
CMD ["gunicorn", "app:app", "--workers", "2", "--timeout", "180", "--bind", "0.0.0.0:10000"]
