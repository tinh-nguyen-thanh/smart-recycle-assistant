import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

# Shortcut: khoa mac dinh chi de chay thu, khi trien khai phai dat bien moi truong SECRET_KEY
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-chi-dung-khi-chay-thu")
ALGORITHM = "HS256"
TOKEN_HOURS = 24
VONG_LAP = 600_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), VONG_LAP).hex()
    return f"pbkdf2${VONG_LAP}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    _, vong, salt, digest = stored.split("$")
    thu = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(vong)).hex()
    return hmac.compare_digest(thu, digest)


def create_token(user_id: int) -> str:
    het_han = datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS)
    return jwt.encode({"sub": str(user_id), "exp": het_han}, SECRET_KEY, algorithm=ALGORITHM)


bearer = HTTPBearer()


def get_current_user(
    cred: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = jwt.decode(cred.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(401, "Token không hợp lệ hoặc hết hạn")
    user = db.get(User, int(payload["sub"]))
    if user is None or user.status != "active":
        raise HTTPException(401, "Tài khoản không tồn tại hoặc bị khóa")
    return user
    