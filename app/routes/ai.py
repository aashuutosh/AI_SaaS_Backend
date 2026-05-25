from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel

from app.database.session import get_db
from app.auth.deps import get_current_user
from app.models.base import User, Role
from app.services.ai_service import generate_and_charge
from loguru import logger

router = APIRouter(prefix="/v1/ai", tags=["AI Engine"])

class ChatRequest(BaseModel):
    prompt: str
    tool_name: str = "chat"

class ChatResponse(BaseModel):
    status: str
    response: str
    remaining_credits: int

@router.post("/chat", response_model=ChatResponse)
async def ai_chat_endpoint(
    request: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Secure endpoint that strictly enforces RBAC before processing AI transactions.
    """
    # 1. Fetch the user's assigned Role and Permissions
    result = await db.execute(select(Role).where(Role.id == user.role_id))
    role = result.scalars().first()
    
    if not role:
        logger.error(f"User {user.id} has an invalid role_id: {user.role_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account configuration error. Please contact support."
        )

    # 2. Strict RBAC Enforcement
    allowed_tools = role.permissions.get("tools", [])
    is_admin = role.permissions.get("admin_access", False)
    
    # If they aren't an admin, and the tool isn't in their tier's tool array, block them.
    if request.tool_name not in allowed_tools and not is_admin:
        logger.warning(f"User {user.id} attempted unauthorized access to tool: {request.tool_name}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Your current plan does not include access to the '{request.tool_name}' tool. Please upgrade."
        )

    # 3. Execute Atomic AI Transaction
    ai_text = await generate_and_charge(db, user, request.prompt, request.tool_name)
    
    return ChatResponse(
        status="success",
        response=ai_text,
        remaining_credits=user.credits
    )