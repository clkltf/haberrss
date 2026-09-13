import time
import psycopg

from .config import settings

MIGRATION = "/app/migrations/001_init.sql"


def main():
    for attempt in range(30):
        try:
            with open(MIGRATION, "r", encoding="utf-8") as f:
                sql = f.read()
            with psycopg.connect(settings.database_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                conn.commit()
            print("database migration ok")
            return
        except Exception as exc:
            print(f"migration retry {attempt + 1}/30: {exc}")
            time.sleep(2)
    raise SystemExit("database migration failed")


if __name__ == "__main__":
    main()
