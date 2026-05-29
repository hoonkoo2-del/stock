"""간단 인증 — 소규모(지인 공유)용. bcrypt 해시 + 세션 쿠키."""
from passlib.context import CryptContext
from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models

pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(p: str) -> str:
    return pwd.hash(p)


def verify_password(p: str, h: str) -> bool:
    try:
        return pwd.verify(p, h)
    except Exception:
        return False


def current_user(request: Request, db: Session = Depends(get_db)) -> models.User:
    uid = request.session.get("uid")
    if not uid:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    user = db.query(models.User).get(uid)
    if not user:
        request.session.clear()
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    return user
