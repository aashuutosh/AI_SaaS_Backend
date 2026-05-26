import google.generativeai as genai
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.models.base import User, Usage
from app.config.settings import get_settings
from loguru import logger

# 1. Load settings and configure the Gemini SDK
settings = get_settings()
genai.configure(api_key=settings.GEMINI_API_KEY)

# Cost mappings based on architectural requirements
# Inside app/services/ai_service.py

# Map your frontend tool names to their exact credit costs
TOOL_COSTS = {
    "chat": 1,
    "short_content": 5,
    "image_generation": 5,
    "long_form_content": 10
}

async def generate_and_charge(db: AsyncSession, user: User, prompt: str, tool_name: str) -> str:
    """
    Executes an atomic transaction that verifies credits, calls the Gemini API, 
    deducts balance, and logs usage. Rolls back entirely on failure.
    """
    cost = TOOL_COSTS.get(tool_name, 1)
    
    # 1. Immediate Credit Check
    if user.credits < cost:
        logger.warning(f"User {user.id} denied {tool_name} access: Insufficient credits.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Insufficient credits to perform this action."
        )

    # 2. External Call to Gemini
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = await model.generate_content_async(prompt)
        response_text = response.text
        token_count = response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else len(response_text.split())
    except Exception as e:
        logger.error(f"Gemini API failure for user {user.id}: {str(e)}")
        # If the API key is invalid, it will fail here and trigger this HTTP Exception
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI generation failed at the upstream provider. Please check API Key."
        )

    # 3. Atomic Database Transaction (Deduct + Log)
    try:
        async with db.begin_nested():
            # Update user credits
            user.credits -= cost
            db.add(user)
            
            # Create usage record
            usage_record = Usage(
                user_id=user.id,
                tool_name=tool_name,
                prompt=prompt,
                response_tokens=token_count,
                credits_used=cost
            )
            db.add(usage_record)
            
        await db.commit()
        logger.info(f"User {user.id} charged {cost} credits for {tool_name}.")
        return response_text
        
    except Exception as e:
        await db.rollback()
        logger.critical(f"Database transaction failed during credit deduction for user {user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transaction failed. No credits were deducted."
        )