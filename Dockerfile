FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

CMD ["python", "app.py", "--host", "0.0.0.0", "--port", "43987", "--endpoint", "wss://kusama-coretime-rpc.polkadot.io/", "--task", "2095"]

