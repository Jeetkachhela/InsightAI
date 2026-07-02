import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.database import engine, Base
from app.core.logging import setup_logging, logger
from app.api.v1 import auth, data_sources, schema, sql, conversations, history, system

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize logging, verify connectivity & extensions (DB-002)
    setup_logging()
    logger.info("Starting up InsightForge AI backend service...")
    
    try:
        async with engine.begin() as conn:
            # Enable vector extension on Neon Postgres
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                logger.info("PostgreSQL pgvector extension verified.")
            except Exception as ext_err:
                logger.warning(f"Could not initialize pgvector extension: {ext_err}. Ensure pgvector is supported if using Postgres.")
                
            # Skip metadata auto creation in production (DB-001)
            if settings.ENV != "production":
                await conn.run_sync(Base.metadata.create_all)
                logger.info("Database schemas and tables initialized successfully (Development mode).")
            else:
                logger.info("Skipping database table auto-creation (Production mode). Migrations must be run via Alembic.")
    except Exception as db_err:
        logger.critical(f"Database startup connectivity check failed: {db_err}")
        # Halt application startup on service dependency check failures
        raise db_err
        
    yield
    
    # Shutdown: Clean up connections
    logger.info("Shutting down InsightForge AI backend service...")
    await engine.dispose()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS configurations - Enforce strict origins, allow Vercel previews dynamically (SEC-004)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.FRONTEND_ORIGINS if settings.FRONTEND_ORIGINS else ["http://localhost:3000"],
    allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:\d+|https://.*\.onrender\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Database Exception Masking (SEC-009)
@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request: Request, exc: SQLAlchemyError):
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.exception(
        f"Database operation failed during {request.method} {request.url.path}: {exc}",
        extra={"request_id": request_id}
    )
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "detail": "A database error occurred while processing your request.",
            "request_id": request_id
        }
    )

# Global Unhandled Exception Masking (SEC-009)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.exception(
        f"Unhandled system error during {request.method} {request.url.path}: {exc}",
        extra={"request_id": request_id}
    )
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "detail": "An internal system error occurred. Please contact the administrator.",
            "request_id": request_id
        }
    )

# Request ID logging middleware
@app.middleware("http")
async def add_request_id_and_log(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    struct_extra = {"request_id": request_id}
    
    logger.info(f"Incoming Request: {request.method} {request.url.path}", extra=struct_extra)
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    
    logger.info(f"Outgoing Response: {response.status_code}", extra=struct_extra)
    return response

# Register Router groups
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(data_sources.router, prefix=f"{settings.API_V1_STR}/data-sources", tags=["data-sources"])
app.include_router(schema.router, prefix=f"{settings.API_V1_STR}/schema", tags=["schema"])
app.include_router(sql.router, prefix=f"{settings.API_V1_STR}/sql", tags=["sql"])
app.include_router(conversations.router, prefix=f"{settings.API_V1_STR}/conversations", tags=["conversations"])
app.include_router(history.router, prefix=f"{settings.API_V1_STR}/history", tags=["history"])
app.include_router(system.router, prefix=f"{settings.API_V1_STR}/system", tags=["system"])


@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "InsightForge AI API",
        "version": "1.0.0",
        "docs_url": "/docs"
    }
