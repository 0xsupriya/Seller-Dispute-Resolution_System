"""Run once to create tables in Neon: python -m backend.app.init_db"""

from backend.app.database import check_db_connection, create_tables, list_tables


def main() -> None:
    ok, message = check_db_connection()
    if not ok:
        raise SystemExit(f"Database not ready: {message}")

    created = create_tables()
    existing = list_tables()
    print("Tables ready:", ", ".join(existing if existing else created))


if __name__ == "__main__":
    main()
