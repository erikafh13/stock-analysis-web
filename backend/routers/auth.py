"""
backend/routers/auth.py
Endpoint login & info user.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from auth import authenticate_user, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    username = authenticate_user(form_data.username, form_data.password)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username atau password salah",
        )
    token = create_access_token(username)
    return TokenResponse(access_token=token, username=username)


@router.get("/me")
def me(current_user: str = Depends(get_current_user)):
    return {"username": current_user}
