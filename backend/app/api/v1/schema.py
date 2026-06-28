from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List, Dict, Any
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.models import User
from app.schemas.schemas import SchemaMetadataResponse, SchemaRelationshipResponse
from app.services.datasource_service import DataSourceService

router = APIRouter()

@router.get("/metadata/{ds_id}", response_model=List[SchemaMetadataResponse])
async def get_metadata(
    ds_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = DataSourceService(db)
    # Check ownership
    ds = await service.get_data_source(ds_id, current_user.id)
    if not ds:
        raise HTTPException(
            status_code=404,
            detail="DataSource not found or access denied."
        )
    return await service.repo.get_metadata(ds_id)

@router.get("/relationships/{ds_id}", response_model=List[SchemaRelationshipResponse])
async def get_relationships(
    ds_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = DataSourceService(db)
    # Check ownership
    ds = await service.get_data_source(ds_id, current_user.id)
    if not ds:
        raise HTTPException(
            status_code=404,
            detail="DataSource not found or access denied."
        )
    return await service.repo.get_relationships(ds_id)

@router.post("/re-index/{ds_id}")
async def trigger_reindex(
    ds_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = DataSourceService(db)
    ds = await service.get_data_source(ds_id, current_user.id)
    if not ds or not ds.connection:
        raise HTTPException(
            status_code=404,
            detail="DataSource not found or connection missing."
        )
        
    conn_dict = {
        "host": ds.connection.host,
        "port": ds.connection.port,
        "username": ds.connection.username,
        "password_encrypted": ds.connection.password_encrypted,
        "database_name": ds.connection.database_name,
        "schema_name": ds.connection.schema_name
    }
    
    try:
        # Clear existing metadata
        await service.repo.clear_metadata(ds_id)
        await service.repo.clear_relationships(ds_id)
        
        # Rediscover schema
        columns_data, relationships_data = await service.discovery_service.discover_schema(conn_dict, ds.type)
        
        metadata_objs = []
        for col in columns_data:
            metadata_objs.append(SchemaMetadata(
                data_source_id=ds_id,
                table_name=col["table_name"],
                column_name=col["column_name"],
                data_type=col["data_type"],
                is_nullable=col["is_nullable"],
                is_primary_key=col["is_primary_key"],
                is_foreign_key=col["is_foreign_key"],
                description=col["description"]
            ))
        await service.repo.save_metadata(metadata_objs)
        
        rel_objs = []
        for rel in relationships_data:
            rel_objs.append(SchemaRelationship(
                data_source_id=ds_id,
                source_table=rel["source_table"],
                source_column=rel["source_column"],
                target_table=rel["target_table"],
                target_column=rel["target_column"]
            ))
        await service.repo.save_relationships(rel_objs)
        
        # Index embedding vectors in RAG
        await service.rag_service.index_schema(db, ds_id)
        
        return {"status": "success", "message": f"Successfully re-indexed {len(metadata_objs)} columns."}
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Re-indexing failed: {e}"
        )
