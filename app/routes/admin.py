from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from typing import List

from app.database.session import get_db
# We now need the base user fetcher, plus your specific admin checkers
from app.auth.deps import get_current_user, require_admin, require_super_admin
from app.models.base import User, Role

# Notice we removed the dependencies=[] from the router level!
# We will lock down each route individually based on the hierarchy.
router = APIRouter(prefix="/v1/admin", tags=["Admin & Super Admin Control Panel"])

# --- Schemas ---
class UserListResponse(BaseModel):
    id: int
    email: str
    name: str
    role_id: int
    credits: int
    # We include the role name so the dashboard can easily show "Free", "Pro", etc.
    role_name: str 

class RoleUpdateRequest(BaseModel):
    new_role_id: int


# ---------------------------------------------------------
# TIER 1: ADMIN DASHBOARD (Admins & Super Admins can access)
# ---------------------------------------------------------

@router.get("/users", response_model=List[UserListResponse])
async def get_all_platform_users(
    admin_user: User = Depends(require_admin), # Requires AT LEAST Admin
    db: AsyncSession = Depends(get_db)
):
    """
    Fetches every user in the database, along with their current tier and credits left.
    Both Admins and Super Admins can view this list on their dashboard.
    """
    # Fetch all users and join with their roles to get the role names
    result = await db.execute(select(User, Role).join(Role, User.role_id == Role.id).order_by(User.id))
    rows = result.all()
    
    # Map the joined data to our response model
    return [
        UserListResponse(
            id=user.id,
            email=user.email,
            name=user.name or "Unknown",
            role_id=user.role_id,
            credits=user.credits,
            role_name=role.role_name
        )
        for user, role in rows
    ]


# ---------------------------------------------------------
# TIER 2: SUPER ADMIN ACTIONS (Strictly Super Admin Only)
# ---------------------------------------------------------

@router.patch("/users/{target_user_id}/role")
async def update_user_role(
    target_user_id: int, 
    request: RoleUpdateRequest, 
    super_admin: User = Depends(require_super_admin), # STRICT LOCK
    db: AsyncSession = Depends(get_db)
):
    """
    Promotes or demotes a user. Only a Super Admin can do this.
    """
    user_result = await db.execute(select(User).where(User.id == target_user_id))
    target_user = user_result.scalars().first()
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")

    role_result = await db.execute(select(Role).where(Role.id == request.new_role_id))
    if not role_result.scalars().first():
        raise HTTPException(status_code=400, detail="Invalid Role ID provided.")

    # Apply the promotion
    target_user.role_id = request.new_role_id
    db.add(target_user)
    await db.commit()
    
    return {"status": "success", "message": f"User {target_user.email} updated to role ID {request.new_role_id}."}


@router.delete("/users/{target_user_id}")
async def delete_user_account(
    target_user_id: int,
    super_admin: User = Depends(require_super_admin), # STRICT LOCK
    db: AsyncSession = Depends(get_db)
):
    """
    Permanently deletes a user from the platform. 
    A standard Admin cannot access this endpoint.
    """
    # 1. Prevent the Super Admin from accidentally deleting themselves
    if target_user_id == super_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own Super Admin account."
        )

    # 2. Find the target user
    user_result = await db.execute(select(User).where(User.id == target_user_id))
    target_user = user_result.scalars().first()
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")

    # 3. Delete them from the database
    await db.delete(target_user)
    await db.commit()
    
    return {"status": "success", "message": f"User {target_user.email} has been permanently deleted."}