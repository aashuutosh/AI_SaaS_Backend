from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from typing import List

from app.database.session import get_db
from app.auth.deps import require_super_admin
from app.models.base import User, Role

# Note how the entire router is protected by the require_super_admin dependency
router = APIRouter(
    prefix="/v1/admin", 
    tags=["Super Admin Control Panel"],
    dependencies=[Depends(require_super_admin)]
)

# --- Schemas ---
class UserListResponse(BaseModel):
    id: int
    email: str
    name: str
    role_id: int
    credits: int

class RoleUpdateRequest(BaseModel):
    new_role_id: int

# --- Endpoints ---
@router.get("/users", response_model=List[UserListResponse])
async def get_all_platform_users(db: AsyncSession = Depends(get_db)):
    """
    Fetches every user in the database. Super Admin only.
    """
    result = await db.execute(select(User).order_by(User.id))
    users = result.scalars().all()
    return users

@router.patch("/users/{target_user_id}/role")
async def update_user_role(
    target_user_id: int, 
    request: RoleUpdateRequest, 
    db: AsyncSession = Depends(get_db)
):
    """
    Promotes or demotes a user by updating their role_id.
    """
    # 1. Verify the target user exists
    user_result = await db.execute(select(User).where(User.id == target_user_id))
    target_user = user_result.scalars().first()
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")

    # 2. Verify the requested role actually exists in our RBAC tiers
    role_result = await db.execute(select(Role).where(Role.id == request.new_role_id))
    if not role_result.scalars().first():
        raise HTTPException(status_code=400, detail="Invalid Role ID provided.")

    # 3. Apply the promotion/demotion
    target_user.role_id = request.new_role_id
    db.add(target_user)
    await db.commit()
    
    return {"status": "success", "message": f"User {target_user.email} updated to role {request.new_role_id}."}