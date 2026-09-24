"""Reset a user's password from an authenticated server environment."""
import argparse
import getpass

from app.database import SessionLocal
from app.models.user import User
from app.services.auth_service import hash_password


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="admin")
    parser.add_argument("--password", help="Omit to enter the password securely at the prompt")
    args = parser.parse_args()
    password = args.password if args.password is not None else getpass.getpass("New password: ")
    if not password:
        parser.error("Password cannot be empty")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == args.user).first()
        if user is None:
            parser.error("User not found")
        user.password_hash = hash_password(password)
        db.commit()
        print(f"Password updated for {args.user}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
