from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from typing import List

from app.database.session import get_db
from app.auth.deps import get_current_user
from app.models.base import User, Role

router = APIRouter(prefix="/v1/subscriptions", tags=["Billing"])

# Define what data we safely expose about our plans
class PlanResponse(BaseModel):
    id: int
    role_name: str
    permissions: dict

@router.get("/plans", response_model=List[PlanResponse])
async def get_available_plans(db: AsyncSession = Depends(get_db)):
    """
    Fetches all available subscription tiers directly from the database.
    This allows you to change permissions dynamically without editing frontend code.
    """
    result = await db.execute(select(Role).order_by(Role.id))
    roles = result.scalars().all()
    return roles

class UpgradeRequest(BaseModel):
    role_id: int

@router.post("/upgrade")
async def simulate_checkout_upgrade(
    request: UpgradeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Simulates a successful payment webhook (e.g., from Stripe or Razorpay).
    Updates the user's role and deposits credits into their account based on the tier.
    """
    # 1. Verify the requested tier actually exists in the database
    result = await db.execute(select(Role).where(Role.id == request.role_id))
    new_role = result.scalars().first()

    if not new_role:
        raise HTTPException(status_code=404, detail="Subscription plan not found.")

    if new_role.role_name == "free":
        raise HTTPException(status_code=400, detail="Cannot upgrade to a free tier.")

    # 2. Assign the new role
    user.role_id = new_role.id
    
    # 3. Deposit the respective credit package
    if new_role.role_name == "starter":
        user.credits += 1000
    elif new_role.role_name == "pro":
        user.credits += 5000
    elif new_role.role_name == "enterprise":
        user.credits += 50000

    # 4. Save the transaction to the database
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return {
        "status": "success", 
        "message": f"Successfully upgraded to {new_role.role_name} plan!",
        "new_credits": user.credits,
        "new_role": new_role.role_name
    }