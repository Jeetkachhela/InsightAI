from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_user, check_rate_limit, get_encryptor
from app.models.models import User
from app.schemas.schemas import (
    QueryRequest, SQLResponse, SQLExecuteRequest, SQLExecuteResponse,
    SQLActionRequest, SQLExplainResponse, SQLOptimizeResponse, SQLDebugResponse
)
from app.services.langgraph_agents import LangGraphAgentsService
from app.services.datasource_service import DataSourceService
from app.agents.nodes import explain_node, optimize_node, debug_node
from app.core.security import is_safe_select_query, CredentialEncryptor, workspace_lock_manager

router = APIRouter()

@router.post(
    "/generate", 
    response_model=SQLResponse,
    dependencies=[Depends(check_rate_limit(limit=10))]
)
async def generate_sql(
    req: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lock = workspace_lock_manager.get_lock(req.data_source_id)
    if lock.locked():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workspace is currently busy processing another request."
        )
    async with lock:
        service = LangGraphAgentsService(db)
        try:
            result = await service.run_workflow(
                user_id=current_user.id,
                ds_id=req.data_source_id,
                user_query=req.nl_query,
                conversation_id=req.conversation_id,
                force_classification="sql_gen"
            )
            return result
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Workflow execution failed: {str(e)}"
            )

@router.post(
    "/execute", 
    response_model=SQLExecuteResponse,
    dependencies=[Depends(check_rate_limit(limit=10))]
)
async def execute_sql(
    req: SQLExecuteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    encryptor: CredentialEncryptor = Depends(get_encryptor)
):
    lock = workspace_lock_manager.get_lock(req.data_source_id)
    if lock.locked():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workspace is currently busy processing another request."
        )
    async with lock:
        service = DataSourceService(db, encryptor)
        try:
            result = await service.execute_query(
                user_id=current_user.id,
                ds_id=req.data_source_id,
                sql=req.sql
            )
            return result
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Execution error: {str(e)}"
            )

@router.post(
    "/explain", 
    response_model=SQLExplainResponse,
    dependencies=[Depends(check_rate_limit(limit=10))]
)
async def explain_sql_query(
    req: SQLActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = DataSourceService(db)
    ds = await service.get_data_source(req.data_source_id, current_user.id)
    if not ds:
        raise HTTPException(status_code=404, detail="DataSource not found or access denied.")
        
    is_safe, reason = is_safe_select_query(req.sql)
    if not is_safe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security Policy Violation: {reason}"
        )
        
    state = {
        "user_query": req.sql,
        "generated_sql": req.sql,
        "schema_context": {},
        "next_agent": "explain",
        "messages": []
    }
    
    result = await explain_node(state)
    return {"explanation": result.get("sql_explanation", "Failed to explain.")}

@router.post(
    "/optimize", 
    response_model=SQLOptimizeResponse,
    dependencies=[Depends(check_rate_limit(limit=10))]
)
async def optimize_sql_query(
    req: SQLActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = DataSourceService(db)
    ds = await service.get_data_source(req.data_source_id, current_user.id)
    if not ds:
        raise HTTPException(status_code=404, detail="DataSource not found or access denied.")
        
    is_safe, reason = is_safe_select_query(req.sql)
    if not is_safe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security Policy Violation: {reason}"
        )
        
    state = {
        "user_query": req.sql,
        "generated_sql": req.sql,
        "next_agent": "optimize",
        "messages": []
    }
    
    result = await optimize_node(state)
    opt = result.get("sql_optimization", {})
    if "error" in opt:
        raise HTTPException(status_code=400, detail=opt["error"])
        
    return {
        "original_sql": opt.get("original_sql", req.sql),
        "optimized_sql": opt.get("optimized_sql", req.sql),
        "performance_analysis": opt.get("performance_analysis", "Failed to optimize."),
        "recommendations": opt.get("recommendations", [])
    }

@router.post(
    "/debug", 
    response_model=SQLDebugResponse,
    dependencies=[Depends(check_rate_limit(limit=10))]
)
async def debug_sql_query(
    req: SQLActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = DataSourceService(db)
    ds = await service.get_data_source(req.data_source_id, current_user.id)
    if not ds:
        raise HTTPException(status_code=404, detail="DataSource not found or access denied.")
        
    state = {
        "user_query": req.sql,
        "generated_sql": req.sql,
        "next_agent": "debug",
        "messages": []
    }
    
    result = await debug_node(state)
    
    corrected = result.get("generated_sql", "")
    is_safe, reason = is_safe_select_query(corrected)
    if not is_safe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security Policy Violation: Debugger generated unsafe code: {reason}"
        )
        
    return {
        "original_sql": req.sql,
        "corrected_sql": corrected,
        "error_detected": "Syntax or logical error",
        "explanation": result.get("sql_explanation", "No explanation.")
    }
