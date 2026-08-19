# ---- المرحلة 1: تثبيت التبعيات ----
FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# ---- المرحلة 2: الصورة النهائية (خفيفة وآمنة) ----
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Africa/Cairo

WORKDIR /app

# نسخ التبعيات من مرحلة البناء (كاش أفضل عند تغيير الكود فقط)
COPY --from=builder /install /usr/local

# مستخدم غير root لأمان أفضل
RUN useradd --create-home --shell /bin/bash ngo
COPY --chown=ngo:ngo . .

EXPOSE 8000

USER ngo

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/login', timeout=4)"

ENTRYPOINT ["/bin/sh", "/app/docker-entrypoint.sh"]