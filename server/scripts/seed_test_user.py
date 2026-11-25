"""Create (or reset) a local TEST account for development.

Run from the server folder with the venv active:
    python -m scripts.seed_test_user

It refuses to run unless ENVIRONMENT=development in server/.env. The account is a normal user
(real bcrypt hash, normal login flow); there is no authentication bypass anywhere in the app.
"""
from app.core.config import get_settings
from app.core.security import hash_password
from app.database.mongo import get_db, init_db, ping
from app.utils.helpers import utcnow

EMAIL = "test@kithi.ai"
PASSWORD = "Test12345"
FULL_NAME = "Test User"


def main() -> None:
    settings = get_settings()
    if settings.environment != "development":
        raise SystemExit("Refusing to create a test account outside development.")
    if not ping():
        raise SystemExit(f"MongoDB is not reachable at {settings.mongodb_uri}. Start MongoDB and try again.")

    init_db()
    now = utcnow()
    result = get_db().users.update_one(
        {"email": EMAIL},
        {
            "$set": {
                "full_name": FULL_NAME,
                "password_hash": hash_password(PASSWORD),
                "is_active": True,
                "updated_at": now,
            },
            "$setOnInsert": {"settings": {}, "created_at": now},
        },
        upsert=True,
    )
    action = "Created" if result.upserted_id else "Reset password for"
    print(f"{action} test account.\n  Email:    {EMAIL}\n  Password: {PASSWORD}")


if __name__ == "__main__":
    main()
