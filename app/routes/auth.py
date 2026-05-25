from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from app.database.session import get_db
from app.models.base import User, Role
from app.auth.jwt import create_access_token, create_refresh_token, decode_token

router = APIRouter(prefix="/v1/auth", tags=["Authentication"])

class GoogleAuthRequest(BaseModel):
    email: str
    name: str
    profile_image: str | None = None
    # Note: In production, you would receive a Google ID Token here and verify it 
    # via the google-auth library. For architecture setup, we accept the payload directly.

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str

@router.post("/google", response_model=TokenResponse)
async def google_oauth_exchange(request: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    """
    Exchanges Google User Data for our platform's internal JWTs.
    If the user does not exist, they are automatically registered.
    """
    # 1. Check if user exists
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalars().first()

    # 2. Register new user if they don't exist
    if not user:
        # Fetch default role (Basic User) - Assuming Role ID 1 exists
        # We will create a script to seed roles later. For now, hardcode fallback to 1.
        user = User(
            email=request.email,
            name=request.name,
            profile_image=request.profile_image,
            role_id=1, 
            credits=50 # Starter credits
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # 3. Generate internal JWTs
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)

@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(request: RefreshRequest):
    """
    Rotates access tokens using a valid refresh token.
    """
    payload = decode_token(request.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token."
        )
        
    user_id = payload.get("sub")
    new_access_token = create_access_token(subject=user_id)
    new_refresh_token = create_refresh_token(subject=user_id)
    
    return TokenResponse(access_token=new_access_token, refresh_token=new_refresh_token)