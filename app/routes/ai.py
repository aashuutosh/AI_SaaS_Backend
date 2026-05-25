from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from loguru import logger

from app.database.session import get_db
from app.auth.deps import get_current_user
from app.models.base import User, Role
from app.services.ai_service import generate_and_charge

# Initialize a local limiter instance for this router
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/v1/ai", tags=["AI Engine"])

class ChatRequest(BaseModel):
    prompt: str
    tool_name: str = "chat"

class ChatResponse(BaseModel):
    status: str
    response: str
    remaining_credits: int

@router.post("/chat", response_model=ChatResponse)
@limiter.limit("10/minute")  # Strict rate limit: 10 requests per 60 seconds per IP
async def ai_chat_endpoint(
    request: Request,            # CRITICAL: Required for slowapi to track the IP
    chat_request: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Secure endpoint that enforces rate limiting and strict RBAC 
    before processing atomic AI transactions.
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
    if chat_request.tool_name not in allowed_tools and not is_admin:
        logger.warning(f"User {user.id} attempted unauthorized access to tool: {chat_request.tool_name}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Your current plan does not include access to the '{chat_request.tool_name}' tool. Please upgrade."
        )

    # 3. Execute Atomic AI Transaction
    ai_text = await generate_and_charge(db, user, chat_request.prompt, chat_request.tool_name)
    
    return ChatResponse(
        status="success",
        response=ai_text,
        remaining_credits=user.credits
    )