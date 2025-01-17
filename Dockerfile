FROM python:3.9-slim

WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt

ENV PYTHONUNBUFFERED=1

CMD ["python3", "video-scheduler.py"]
