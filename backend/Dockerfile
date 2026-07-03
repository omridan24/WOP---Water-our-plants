FROM python:3.12-slim

# Install Bluetooth dependencies for bleak on Linux
RUN apt-get update && apt-get install -y \
    bluetooth bluez libglib2.0-dev libdbus-1-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Create data directories
RUN mkdir -p /app/data/images

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
