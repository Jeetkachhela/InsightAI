from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List
from app.core.database import get_db
from app.api.deps import get_current_user, check_rate_limit
from app.models.models import User, Conversation
from app.schemas.schemas import ConversationCreate, ConversationResponse
from app.repositories.repositories import ConversationRepository

router = APIRouter()

@router.post(
    "/", 
    response_model=ConversationResponse, 
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_rate_limit(limit=20))]
)
async def create_conversation(
    conv_in: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    repo = ConversationRepository(db)
    db_conv = Conversation(
        user_id=current_user.id,
        title=conv_in.title
    )
    return await repo.create(db_conv)

@router.get("/", response_model=List[ConversationResponse])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    repo = ConversationRepository(db)
    return await repo.list_by_user(current_user.id)

@router.get("/{conv_id}", response_model=ConversationResponse)
async def get_conversation_details(
    conv_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    repo = ConversationRepository(db)
    conv = await repo.get_by_id(conv_id, current_user.id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or access denied."
        )
    return conv
