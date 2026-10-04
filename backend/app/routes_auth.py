from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .limits import limiter
from .models import User
from .security import (
    COOKIE_NAME,
    burn_time,
    create_token,
    current_user,
    hash_password,
    set_auth_cookie,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class Registration(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


def _public(user: User) -> dict:
    return {"id": user.id, "email": user.email, "role": user.role}


@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, body: Credentials, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None:
        burn_time(body.password)
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    set_auth_cookie(response, create_token(user))
    return _public(user)


@router.post("/register", status_code=201)
@limiter.limit("10/hour")
def register(request: Request, body: Registration, response: Response, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="That email is already registered")
    user = User(email=email, password_hash=hash_password(body.password), role="vendor")  # never admin
    db.add(user)
    db.commit()
    set_auth_cookie(response, create_token(user))
    return _public(user)


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return _public(user)
