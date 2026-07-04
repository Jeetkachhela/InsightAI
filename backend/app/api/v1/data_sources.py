from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List
from app.core.database import get_db
from app.api.deps import get_current_user, check_rate_limit, get_encryptor
from app.models.models import User
from app.schemas.schemas import DataSourceCreate, DataSourceResponse
from app.services.datasource_service import DataSourceService
from app.core.security import CredentialEncryptor

router = APIRouter()

@router.post(
    "/", 
    response_model=DataSourceResponse, 
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_rate_limit(limit=10))]
)
async def create_data_source(
    ds_in: DataSourceCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    encryptor: CredentialEncryptor = Depends(get_encryptor)
):
    service = DataSourceService(db, encryptor)
    try:
        # Create datasource connection configurations record (fast)
        created = await service.create_data_source_record(current_user.id, ds_in)
        
        # Schedule discovery and embedding vector indexing in a background task (AI-001)
        background_tasks.add_task(
            service.discover_and_index_background,
            current_user.id,
            created.id,
            ds_in.connection_details.password
        )
        return created
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)  # ValueError from our own validation (e.g. duplicate check) — safe
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to connect and save data source. Please verify your connection details and try again."
        )

@router.get("/", response_model=List[DataSourceResponse])
async def list_data_sources(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    encryptor: CredentialEncryptor = Depends(get_encryptor)
):
    service = DataSourceService(db, encryptor)
    return await service.list_data_sources(current_user.id)

@router.get("/{ds_id}", response_model=DataSourceResponse)
async def get_data_source_details(
    ds_id: UUID,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    encryptor: CredentialEncryptor = Depends(get_encryptor)
):
    service = DataSourceService(db, encryptor)
    ds = await service.get_data_source(ds_id, current_user.id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DataSource not found or access denied."
        )
    # Set ETag header (SEC-008)
    response.headers["ETag"] = f'W/"{ds.id}:{ds.version}"'
    return ds

@router.delete(
    "/{ds_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(check_rate_limit(limit=10))]
)
async def delete_data_source(
    ds_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    encryptor: CredentialEncryptor = Depends(get_encryptor)
):
    service = DataSourceService(db, encryptor)
    ds = await service.get_data_source(ds_id, current_user.id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DataSource not found or access denied."
        )
        
    # Optimistic locking Check (SEC-008)
    if_match = request.headers.get("If-Match")
    if if_match:
        expected_etag = f'W/"{ds.id}:{ds.version}"'
        if if_match != expected_etag:
            raise HTTPException(
                status_code=status.HTTP_412_PRECONDITION_FAILED,
                detail="Precondition Failed: Resource has been modified."
            )
            
    try:
        from sqlalchemy.orm.exc import StaleDataError
        await service.delete_data_source(current_user.id, ds_id)
        return None
    except StaleDataError:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Precondition Failed: Concurrent update detected."
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete data source. Please try again."
        )
