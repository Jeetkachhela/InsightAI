import re
from typing import Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.models import SchemaMetadata, SchemaRelationship
from app.core.logging import logger

class RAGService:
    async def index_schema(self, db: AsyncSession, data_source_id: UUID) -> None:
        """
        Metadata indexing is handled synchronously during schema discovery.
        This method is kept as a no-op to maintain compatibility with workspace agents.
        """
        logger.info(f"Skipping vector embedding generation for data source {data_source_id} (pure keyword context mode enabled).")
        return

    async def retrieve_context(self, db: AsyncSession, data_source_id: UUID, query: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Retrieves schema context using a lightweight, highly reliable, 
        and zero-memory database metadata keyword search.
        """
        logger.info(f"Retrieving schema context via database keyword matching for query: '{query}'")
        
        # 1. Tokenize query and remove standard SQL / English stopwords
        words = re.findall(r"\b[a-zA-Z0-9_]+\b", query.lower())
        stopwords = {
            "how", "many", "are", "there", "is", "a", "the", "of", "in", "for", "to", "with", 
            "on", "at", "by", "from", "an", "select", "find", "show", "get", "list", "query", 
            "sql", "database", "where", "filter", "having", "group", "by", "order", "limit",
            "count", "sum", "avg", "min", "max"
        }
        keywords = [w for w in words if w not in stopwords and len(w) > 1]
        
        tables = set()
        
        if not keywords:
            logger.info("No search keywords identified in query. Retrieving all available tables.")
            all_tables_res = await db.execute(
                select(SchemaMetadata.table_name)
                .where(SchemaMetadata.data_source_id == data_source_id)
                .distinct()
            )
            tables = set(all_tables_res.scalars().all())
        else:
            from sqlalchemy import or_
            conditions = []
            for kw in keywords:
                conditions.append(SchemaMetadata.table_name.ilike(f"%{kw}%"))
                conditions.append(SchemaMetadata.column_name.ilike(f"%{kw}%"))
                
            match_res = await db.execute(
                select(SchemaMetadata.table_name)
                .where(SchemaMetadata.data_source_id == data_source_id)
                .where(or_(*conditions))
                .distinct()
            )
            tables = set(match_res.scalars().all())
            
            # If no tables matched the keywords, default to retrieving all tables
            if not tables:
                all_tables_res = await db.execute(
                    select(SchemaMetadata.table_name)
                    .where(SchemaMetadata.data_source_id == data_source_id)
                    .distinct()
                )
                tables = set(all_tables_res.scalars().all())

        # 2. Fetch column details for matched tables
        tables_list = list(tables)
        if not tables_list:
            return {"tables": {}, "relationships": []}
            
        metadata_result = await db.execute(
            select(SchemaMetadata)
            .where(SchemaMetadata.data_source_id == data_source_id, SchemaMetadata.table_name.in_(tables_list))
        )
        metadata_fields = metadata_result.scalars().all()
        
        # 3. Fetch relationships between matched tables
        rel_result = await db.execute(
            select(SchemaRelationship)
            .where(
                SchemaRelationship.data_source_id == data_source_id,
                SchemaRelationship.source_table.in_(tables_list) | SchemaRelationship.target_table.in_(tables_list)
            )
        )
        relationships = rel_result.scalars().all()
        
        # 4. Format schema context response
        tables_context = {}
        for field in metadata_fields:
            tables_context.setdefault(field.table_name, []).append({
                "column_name": field.column_name,
                "data_type": field.data_type,
                "is_nullable": field.is_nullable,
                "is_primary_key": field.is_primary_key,
                "is_foreign_key": field.is_foreign_key,
                "description": field.description
            })
            
        rel_context = []
        for rel in relationships:
            rel_context.append({
                "source_table": rel.source_table,
                "source_column": rel.source_column,
                "target_table": rel.target_table,
                "target_column": rel.target_column
            })
            
        return {
            "tables": tables_context,
            "relationships": rel_context
        }
