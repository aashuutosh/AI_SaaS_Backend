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

# ---------------------------------------------------------
# SCHEMAS
# ---------------------------------------------------------
class ChatRequest(BaseModel):
    prompt: str
    tool_name: str = "chat"

class ChatResponse(BaseModel):
    status: str
    response: str
    remaining_credits: int

class SummarizeRequest(BaseModel):
    document_text: str
    tool_name: str = "summarizer"

class SummarizeResponse(BaseModel):
    status: str
    summary: str
    remaining_credits: int

class ImageRequest(BaseModel):
    prompt: str
    style: str = "realistic"
    tool_name: str = "image_generation"

class ImageResponse(BaseModel):
    status: str
    image_url: str
    remaining_credits: int

class LongFormRequest(BaseModel):
    topic: str
    tool_name: str = "long_form_content" # Must match your TOOL_COSTS dictionary exactly!

class LongFormResponse(BaseModel):
    status: str
    article: str
    remaining_credits: int


# ---------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------

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

@router.post("/summarize", response_model=SummarizeResponse)
@limiter.limit("5/minute") # Stricter rate limit for heavier processing
async def ai_summarize_endpoint(
    request: Request,
    summarize_request: SummarizeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Compresses long text. Costs more credits than a standard chat."""
    result = await db.execute(select(Role).where(Role.id == user.role_id))
    role = result.scalars().first()
    
    allowed_tools = role.permissions.get("tools", [])
    is_admin = role.permissions.get("admin_access", False)
    
    if summarize_request.tool_name not in allowed_tools and not is_admin:
        logger.warning(f"User {user.id} attempted unauthorized access to tool: {summarize_request.tool_name}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your current plan does not include the Document Summarizer. Please upgrade."
        )

    summary_text = await generate_and_charge(db, user, summarize_request.document_text, summarize_request.tool_name)
    
    return SummarizeResponse(
        status="success",
        summary=summary_text,
        remaining_credits=user.credits
    )

@router.post("/image", response_model=ImageResponse)
@limiter.limit("2/minute") # Extremely strict limit for expensive image generation
async def ai_image_endpoint(
    request: Request,
    image_request: ImageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generates an image from a prompt. High credit cost."""
    result = await db.execute(select(Role).where(Role.id == user.role_id))
    role = result.scalars().first()
    
    allowed_tools = role.permissions.get("tools", [])
    is_admin = role.permissions.get("admin_access", False)
    
    if image_request.tool_name not in allowed_tools and not is_admin:
        logger.warning(f"User {user.id} attempted unauthorized access to tool: {image_request.tool_name}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Image Generation is a Pro-tier feature. Please upgrade your account."
        )

    # Combine style and prompt for the AI service
    combined_prompt = f"Style: {image_request.style} - {image_request.prompt}"
    generated_image_url = await generate_and_charge(db, user, combined_prompt, image_request.tool_name)
    
    return ImageResponse(
        status="success",
        image_url=generated_image_url,
        remaining_credits=user.credits
    )

@router.post("/long-form", response_model=LongFormResponse)
@limiter.limit("3/minute") # Strict limit for heavy generations
async def ai_long_form_endpoint(
    request: Request,
    long_form_request: LongFormRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generates comprehensive, multi-paragraph articles. Premium credit cost."""
    # 1. Fetch Role & Permissions
    result = await db.execute(select(Role).where(Role.id == user.role_id))
    role = result.scalars().first()
    
    allowed_tools = role.permissions.get("tools", [])
    is_admin = role.permissions.get("admin_access", False)
    
    # 2. RBAC Check
    if long_form_request.tool_name not in allowed_tools and not is_admin:
        logger.warning(f"User {user.id} attempted unauthorized access to tool: {long_form_request.tool_name}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Long-form article generation is a premium feature. Please upgrade your account."
        )

    # 3. Execute & Charge
    article_text = await generate_and_charge(db, user, long_form_request.topic, long_form_request.tool_name)
    
    return LongFormResponse(
        status="success",
        article=article_text,
        remaining_credits=user.credits
    )