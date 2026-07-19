from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.models import User
from app.repositories.repositories import QueryLogRepository
from app.schemas.schemas import SQLExecuteResponse  # Reuse query schemas or define custom

router = APIRouter()

# Let's return structured query logs
@router.get("/query-logs")
async def get_query_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    repo = QueryLogRepository(db)
    logs = await repo.list_by_user(current_user.id)
    return [
        {
            "id": log.id,
            "query_text": log.query_text,
            "status": log.status,
            "execution_time_ms": log.execution_time_ms,
            "created_at": log.created_at
        } for log in logs
    ]

@router.delete("/query-logs/{log_id}")
async def delete_query_log(
    log_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    repo = QueryLogRepository(db)
    deleted = await repo.delete_by_id(log_id, current_user.id)
    if not deleted:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Query log not found or access denied.")
    return {"detail": "Query log deleted successfully"}

@router.delete("/query-logs")
async def clear_query_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    repo = QueryLogRepository(db)
    await repo.clear_all_by_user(current_user.id)
    return {"detail": "All query logs cleared successfully"}
