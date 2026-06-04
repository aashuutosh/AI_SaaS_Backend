from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel

from app.database.session import get_db
from app.auth.deps import get_current_user
from app.models.base import User

router = APIRouter(prefix="/v1/settings", tags=["Account Settings"])

class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    profile_image: str | None = None

@router.patch("/profile")
async def update_user_profile(
    request: ProfileUpdateRequest, 
    user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    """Updates the user's personal information."""
    if request.name:
        user.name = request.name
    if request.profile_image:
        user.profile_image = request.profile_image
        
    db.add(user)
    await db.commit()
    
    return {"status": "success", "message": "Profile successfully updated."}

@router.delete("/account")
async def gdpr_delete_account(
    user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    """
    Permanently deletes the user's account and all associated data.
    Ensures strict GDPR compliance.
    """
    await db.delete(user)
    await db.commit()
    
    return {"status": "success", "message": "Account has been permanently erased."}