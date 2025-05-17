FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY to_kafka.py .

ENV PYTHONUNBUFFERED=1
CMD ["python", "to_kafka.py"]
