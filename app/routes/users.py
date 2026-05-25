from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.auth.deps import get_current_user
from app.models.base import User

router = APIRouter(prefix="/v1/users", tags=["Users"])

# Define exactly what data we safely expose to the frontend
class UserProfileResponse(BaseModel):
    id: int
    email: str
    name: str
    profile_image: str | None
    role_id: int
    credits: int

@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(current_user: User = Depends(get_current_user)):
    """
    Retrieves the profile and live credit balance of the authenticated user.
    """
    return current_user