FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY biomebeacon_bot ./biomebeacon_bot

CMD ["python", "-m", "biomebeacon_bot"]
