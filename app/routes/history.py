from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from pydantic import BaseModel
from datetime import datetime

from app.database.session import get_db
from app.auth.deps import get_current_user
from app.models.base import User
# Assuming you have a Usage or History model in your base.py that tracks generations
from app.models.base import Usage 

router = APIRouter(prefix="/v1/history", tags=["User History"])

# Define the precise data structure we return to the frontend
class HistoryItemResponse(BaseModel):
    id: int
    tool_used: str
    prompt: str
    result_text: str
    cost: int
    created_at: datetime

@router.get("/", response_model=List[HistoryItemResponse])
async def get_user_history(
    limit: int = 20,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetches a paginated list of the user's past AI generations.
    """
    # Query the database for this specific user's usage history, newest first
    query = (
        select(Usage)
        .where(Usage.user_id == user.id)
        .order_by(Usage.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    
    result = await db.execute(query)
    history_records = result.scalars().all()
    
    # Map the database records to our secure Pydantic response model
    return [
        HistoryItemResponse(
            id=record.id,
            tool_used=record.tool_name,
            prompt=record.prompt,
            result_text=record.result_text,
            cost=record.cost,
            created_at=record.created_at
        )
        for record in history_records
    ]

@router.delete("/{history_id}")
async def delete_history_item(
    history_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Allows a user to delete a specific past generation from their dashboard.
    """
    query = select(Usage).where(Usage.id == history_id, Usage.user_id == user.id)
    result = await db.execute(query)
    record = result.scalars().first()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="History record not found or you do not have permission to delete it."
        )
        
    await db.delete(record)
    await db.commit()
    
    return {"status": "success", "message": "Record deleted successfully"}