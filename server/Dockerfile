FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY biomebeacon_server ./biomebeacon_server

EXPOSE 8400
CMD ["python", "-m", "biomebeacon_server"]
