#!/bin/sh
# نقطة دخول الحاوية: انتظار جاهزية قاعدة البيانات ثم تشغيل uvicorn
set -e

echo "[entrypoint] انتظار جاهزية PostgreSQL ..."
python - <<'PY'
import os, sys, time
import psycopg2

url = os.getenv("DATABASE_URL", "")
for attempt in range(30):
    try:
        conn = psycopg2.connect(url)
        conn.close()
        print("[entrypoint] قاعدة البيانات جاهزة.")
        sys.exit(0)
    except Exception as e:
        print(f"[entrypoint] المحاولة {attempt + 1}/30: {e}")
        time.sleep(2)
print("[entrypoint] فشل الاتصال بقاعدة البيانات خلال المهلة المحددة.")
sys.exit(1)
PY

echo "[entrypoint] تشغيل خادم uvicorn ..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${WEB_PORT:-8000}" --workers "${WEB_WORKERS:-1}"