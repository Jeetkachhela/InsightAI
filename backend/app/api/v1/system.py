import httpx
import time
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, func
from app.core.logging import logger
from sqlalchemy.future import select
from datetime import datetime
from app.core.database import get_db
from app.core.config import settings
from app.models.models import User, DataSource, SchemaEmbedding, Message, QueryLog, AuditLog

router = APIRouter()

START_TIME = datetime.utcnow()

async def check_groq_connectivity() -> str:
    """
    Lightweight health check pinging api.groq.com models list to verify API key authenticity.
    """
    if not settings.GROQ_API_KEY or "gsk_" not in settings.GROQ_API_KEY:
        return "not-configured (mock mode active)"
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                timeout=3.0
            )
            if res.status_code == 200:
                return "healthy"
            else:
                return f"unhealthy (status {res.status_code})"
    except Exception as e:
        logger.error(f"Groq connectivity check failed: {e}")
        return "unhealthy: connection failed"

@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Detailed system health status check (DB-004) verifying DB query, pgvector count, and Groq connectivity.
    """
    # 1. Check DB connectivity
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy: connection failed"
        
    # 2. Check Vector store (pgvector)
    vector_status = "healthy"
    try:
        res = await db.execute(select(func.count(SchemaEmbedding.id)))
        emb_count = res.scalar() or 0
        vector_status = f"healthy ({emb_count} embeddings)"
    except Exception as e:
        logger.error(f"Vector store health check failed: {e}")
        vector_status = "unhealthy: count query failed"
        
    # 3. Check Groq Connectivity
    groq_status = await check_groq_connectivity()
    
    overall = "healthy"
    if "unhealthy" in db_status or "unhealthy" in vector_status or "unhealthy" in groq_status:
        overall = "unhealthy"
        
    return {
        "status": overall,
        "timestamp": datetime.utcnow(),
        "database": db_status,
        "vector_store": vector_status,
        "groq": groq_status,
        "version": "1.0.0"
    }

@router.get("/metrics")
async def get_metrics(db: AsyncSession = Depends(get_db)):
    """
    Detailed runtime and resource metrics tracking (ARCH-003, ARCH-004) covering latency, tokens, error rates.
    """
    # 1. System stats
    uptime_seconds = int((datetime.utcnow() - START_TIME).total_seconds())
    
    # 2. Users count
    user_res = await db.execute(select(func.count(User.id)))
    user_count = user_res.scalar() or 0
    
    # 3. Data sources count
    ds_res = await db.execute(select(func.count(DataSource.id)))
    ds_count = ds_res.scalar() or 0
    
    # 4. Schema Embeddings count
    emb_res = await db.execute(select(func.count(SchemaEmbedding.id)))
    emb_count = emb_res.scalar() or 0
    
    # 5. SQL Executions metrics (ARCH-003)
    query_stats = await db.execute(
        select(
            func.count(QueryLog.id),
            func.sum(QueryLog.execution_time_ms),
            func.sum(text("CASE WHEN status = 'error' THEN 1 ELSE 0 END"))
        )
    )
    q_count, q_total_time, q_errors = query_stats.fetchone()
    q_count = q_count or 0
    q_total_time = q_total_time or 0
    q_errors = q_errors or 0
    
    avg_query_time_ms = int(q_total_time / q_count) if q_count > 0 else 0
    query_error_rate = (q_errors / q_count * 100) if q_count > 0 else 0.0
    
    # 6. AI & Token Resource Tracking (ARCH-004)
    # Sum character length of prompts and responses divided by 4 as a standard token approximation
    token_stats = await db.execute(
        select(
            func.count(Message.id),
            func.sum(func.length(Message.content))
        )
    )
    ai_msg_count, total_char_len = token_stats.fetchone()
    ai_msg_count = ai_msg_count or 0
    total_char_len = total_char_len or 0
    
    # Divide total chars by 4 to estimate tokens (rough proxy)
    estimated_tokens_consumed = int(total_char_len / 4)
    
    return {
        "uptime_seconds": uptime_seconds,
        "registered_users": user_count,
        "datasources": ds_count,
        "schema_embeddings": emb_count,
        "query_execution": {
            "total_queries_run": q_count,
            "failed_queries": q_errors,
            "error_rate_pct": round(query_error_rate, 2),
            "average_latency_ms": avg_query_time_ms
        },
        "ai_usage": {
            "total_ai_queries_run": ai_msg_count,
            "estimated_tokens_consumed": estimated_tokens_consumed
        }
    }

@router.get("/readiness")
async def readiness_check(response: Response, db: AsyncSession = Depends(get_db)):
    """
    Readiness probe verifying DB query execution, Alembic migrations status, and Groq API readiness.
    """
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        logger.error(f"Readiness check failed: DB query execution failed: {e}")
        
    migrations_ok = False
    try:
        res = await db.execute(text("SELECT version_num FROM alembic_version"))
        version = res.scalar()
        if version:
            migrations_ok = True
    except Exception as e:
        logger.error(f"Readiness check failed: migrations check failed: {e}")
        
    groq_ok = False
    groq_status = await check_groq_connectivity()
    if "unhealthy" not in groq_status:
        groq_ok = True
        
    overall = db_ok and migrations_ok and groq_ok
    if not overall:
        response.status_code = 503
        
    return {
        "status": "ready" if overall else "not-ready",
        "database": "ready" if db_ok else "down",
        "migrations": "ready" if migrations_ok else "down",
        "groq": "ready" if groq_ok else "down"
    }
