FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Diretório para certificados montados via Kubernetes Secret
RUN mkdir -p /app/certs

EXPOSE 5009

CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
