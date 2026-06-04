import urllib.parse
import google.generativeai as genai
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.models.base import User, Usage
from app.config.settings import get_settings
from loguru import logger

# 1. Load settings and configure the Gemini SDK
settings = get_settings()
genai.configure(api_key=settings.GEMINI_API_KEY)

# Map your frontend tool names to their exact credit costs
TOOL_COSTS = {
    "chat": 1,
    "short_content": 5,
    "image_generation": 5,
    "long_form_content": 10
}

async def generate_and_charge(db: AsyncSession, user: User, prompt: str, tool_name: str) -> str:
    """
    Executes an atomic transaction that verifies credits, calls the AI API, 
    deducts balance, and logs usage. Rolls back entirely on failure.
    """
    # Default to 1 if tool not found, though RBAC usually catches this first
    cost = TOOL_COSTS.get(tool_name, 1)
    
    # 1. Immediate Credit Check
    if user.credits < cost:
        logger.warning(f"User {user.id} denied {tool_name} access: Insufficient credits.")
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, 
            detail=f"Insufficient credits. This tool requires {cost} credits."
        )

    # 2. AI Generation Routing
    try:
        # --- IMAGE GENERATION ROUTE ---
        if tool_name == "image_generation":
            # Since Gemini Flash is a text model, we use a free URL-based API to return a real image file.
            safe_prompt = urllib.parse.quote(prompt)
            response_text = f"https://image.pollinations.ai/prompt/{safe_prompt}?nologo=true"
            token_count = 0 # Images don't use text tokens

        # --- TEXT GENERATION ROUTE (GEMINI) ---
        else:
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            # Contextualize the prompt so Gemini knows how to behave
            final_prompt = prompt
            if tool_name == "short_content":
                final_prompt = f"Write a very short, engaging, and concise piece of content about: {prompt}"
            elif tool_name == "long_form_content":
                final_prompt = f"Write a highly detailed, comprehensive, and well-structured long-form article about: {prompt}"
                
            response = await model.generate_content_async(final_prompt)
            response_text = response.text
            
            if hasattr(response, 'usage_metadata'):
                token_count = response.usage_metadata.candidates_token_count 
            else:
                token_count = len(response_text.split())

    except Exception as e:
        logger.error(f"AI API failure for user {user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI generation failed at the upstream provider. Please try again."
        )

    # 3. Atomic Database Transaction (Deduct + Log)
    try:
        async with db.begin_nested():
            # Update user credits
            user.credits -= cost
            db.add(user)
            
            # Create usage record (using your exact schema!)
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