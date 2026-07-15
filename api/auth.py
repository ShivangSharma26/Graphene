import os
import httpx
import jwt
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse
from datetime import datetime, timedelta
from typing import Optional
from .db import get_or_create_user, get_recent_searches

router = APIRouter()

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-graphene-key-1234")
JWT_ALGORITHM = "HS256"

# Frontend URL
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

@router.get("/login/github")
async def github_login():
    """Redirects the user to GitHub's OAuth authorization page."""
    if not GITHUB_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GitHub Client ID not configured.")
    
    github_auth_url = f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&scope=read:user"
    return RedirectResponse(url=github_auth_url)

@router.get("/callback/github")
async def github_callback(code: str):
    """Handles the GitHub OAuth callback, exchanges code for token, and fetches user info."""
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured properly.")

    # 1. Exchange code for access token
    async with httpx.AsyncClient(timeout=30.0) as client:
        token_res = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code
            },
            headers={"Accept": "application/json"}
        )
        token_data = token_res.json()
        
        if "error" in token_data:
            raise HTTPException(status_code=400, detail=token_data["error_description"])
            
        access_token = token_data["access_token"]
        
        # 2. Fetch user profile from GitHub
        user_res = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        user_data = user_res.json()
        
        github_id = str(user_data["id"])
        username = user_data["login"]
        avatar_url = user_data.get("avatar_url", "")
        
        # 3. Store user in SQLite
        get_or_create_user(github_id, username, avatar_url)
        
        # 4. Generate internal JWT token
        payload = {
            "sub": github_id,
            "username": username,
            "avatar": avatar_url,
            "exp": datetime.utcnow() + timedelta(days=7)
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        # 5. Redirect back to frontend with token
        return RedirectResponse(url=f"{FRONTEND_URL}/auth/callback?token={token}")

@router.get("/me")
async def get_current_user(token: str):
    """Returns the current user profile and recent searches based on JWT."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        github_id = payload.get("sub")
        
        # Fetch recent searches
        recent_searches = get_recent_searches(github_id)
        
        return {
            "user": payload,
            "recent_searches": recent_searches
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
