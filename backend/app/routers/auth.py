from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import create_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

EMAIL_PATTERN = r"^[^\s@]+@[^\s@]+\.[^\s@]+$" # cùng biểu thức kiểm tra với login.html


class RegisterIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    email: str = Field(max_length=100, pattern=EMAIL_PATTERN)
    password: str = Field(min_length=8, max_length=128)



class LoginIn(BaseModel):
    email: str
    password: str


def _user_out(user: User) -> dict:
    return {"id": user.id, "name": user.display_name, "email": user.email}



def _token_out(user: User) -> dict:
    return {"token": create_token(user.id), "user": _user_out(user)}


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: Session= Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Email này đã được đăng ký. Hãy đăng nhập.")
    user = User(email=email, password_hash=hash_password(body.password), display_name=body.name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_out(user)


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Email hoặc mật khẩu chưa đúng.")
    if user.status != "active":
        raise HTTPException(403, "Tài khoản đã bị khóa.")
    return _token_out(user)

@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return _user_out(user)