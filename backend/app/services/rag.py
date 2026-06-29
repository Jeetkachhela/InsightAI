import hashlib
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.models import SchemaMetadata, SchemaRelationship, SchemaEmbedding
from app.core.logging import logger

class RAGService:
    _model = None

    @classmethod
    def _get_model(cls):
        """
        Lazily initialize and load the SentenceTransformer model to avoid 
        overhead during startup when importing.
        """
        if cls._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info("Initializing SentenceTransformer model 'all-MiniLM-L6-v2'...")
                cls._model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("SentenceTransformer model successfully loaded.")
            except ImportError:
                logger.error("Failed to import sentence-transformers. Please run pip install sentence-transformers.")
                raise
        return cls._model

    def get_embedding(self, text: str) -> List[float]:
        """
        Generates a 384-dimensional vector embedding for the input text.
        """
        model = self._get_model()
        embedding = model.encode(text)
        return embedding.tolist()

    async def index_schema(self, db: AsyncSession, data_source_id: UUID) -> None:
        """
        Retrieves schema metadata for a data source, formats descriptions, 
        generates embeddings, and saves them to the schema_embeddings table.
        Performs caching (AI-002) and incremental re-indexing (AI-003).
        """
        logger.info(f"Indexing schema metadata for data source: {data_source_id}")
        
        # 1. Fetch metadata columns
        result = await db.execute(
            select(SchemaMetadata).where(SchemaMetadata.data_source_id == data_source_id)
        )
        columns = result.scalars().all()
        
        if not columns:
            logger.warning(f"No metadata found to index for data source {data_source_id}.")
            return
            
        # Group columns by table to make table-level embeddings
        tables_map = {}
        for col in columns:
            tables_map.setdefault(col.table_name, []).append(col)
            
        # 2. Fetch existing embeddings for incremental reindexing (AI-003)
        existing_result = await db.execute(
            select(SchemaEmbedding).where(SchemaEmbedding.data_source_id == data_source_id)
        )
        existing_embs = existing_result.scalars().all()
        existing_map = {(e.entity_type, e.entity_name): e for e in existing_embs}
        
        processed_keys = set()
        
        # 3. Process Table level embeddings
        for table_name, table_cols in tables_map.items():
            col_list_str = ", ".join([f"{c.column_name} ({c.data_type})" for c in table_cols])
            table_desc = f"Table: {table_name}. Description: database table containing fields: {col_list_str}."
            table_fingerprint = hashlib.sha256(table_desc.encode("utf-8")).hexdigest()
            
            key = ("table", table_name)
            processed_keys.add(key)
            
            if key in existing_map:
                existing_emb = existing_map[key]
                # Cache match: skip embedding generation (AI-002)
                if existing_emb.fingerprint == table_fingerprint:
                    logger.info(f"Embedding cache hit for table: {table_name}")
                else:
                    logger.info(f"Embedding cache miss (modified description) for table: {table_name}")
                    existing_emb.description = table_desc
                    existing_emb.fingerprint = table_fingerprint
                    existing_emb.embedding = self.get_embedding(table_desc)
                    db.add(existing_emb)
            else:
                logger.info(f"Generating new embedding for table: {table_name}")
                vector = self.get_embedding(table_desc)
                emb_obj = SchemaEmbedding(
                    data_source_id=data_source_id,
                    entity_type="table",
                    entity_name=table_name,
                    description=table_desc,
                    fingerprint=table_fingerprint,
                    embedding=vector
                )
                db.add(emb_obj)
            
            # 4. Process Column level embeddings
            for col in table_cols:
                pk_str = "Primary Key" if col.is_primary_key else ""
                fk_str = "Foreign Key" if col.is_foreign_key else ""
                constraints = " ".join(filter(None, [pk_str, fk_str]))
                col_desc = f"Table: {col.table_name}, Column: {col.column_name}, Type: {col.data_type}. {constraints}. Description: {col.description or 'No description available'}"
                col_fingerprint = hashlib.sha256(col_desc.encode("utf-8")).hexdigest()
                
                col_key = ("column", f"{col.table_name}.{col.column_name}")
                processed_keys.add(col_key)
                
                if col_key in existing_map:
                    existing_emb = existing_map[col_key]
                    # Cache match: skip embedding generation (AI-002)
                    if existing_emb.fingerprint == col_fingerprint:
                        pass
                    else:
                        logger.info(f"Embedding cache miss for column: {col.table_name}.{col.column_name}")
                        existing_emb.description = col_desc
                        existing_emb.fingerprint = col_fingerprint
                        existing_emb.embedding = self.get_embedding(col_desc)
                        db.add(existing_emb)
                else:
                    vector = self.get_embedding(col_desc)
                    emb_obj = SchemaEmbedding(
                        data_source_id=data_source_id,
                        entity_type="column",
                        entity_name=f"{col.table_name}.{col.column_name}",
                        description=col_desc,
                        fingerprint=col_fingerprint,
                        embedding=vector
                    )
                    db.add(emb_obj)
                    
        # 5. Delete removed entities (AI-003)
        for key, existing_emb in existing_map.items():
            if key not in processed_keys:
                logger.info(f"Removing obsolete schema embedding for: {key[1]}")
                await db.delete(existing_emb)
                
        await db.commit()
        logger.info("Successfully completed incremental schema embedding re-indexing.")

    async def retrieve_context(self, db: AsyncSession, data_source_id: UUID, query: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Computes query embedding, searches schema_embeddings using pgvector,
        and constructs a schema context representation.
        """
        logger.info(f"Retrieving schema context for query: '{query}'")
        
        query_vector = self.get_embedding(query)
        
        # Query pgvector for closest embeddings
        result = await db.execute(
            select(SchemaEmbedding)
            .where(SchemaEmbedding.data_source_id == data_source_id)
            .order_by(SchemaEmbedding.embedding.cosine_distance(query_vector))
            .limit(top_k)
        )
        similar_items = result.scalars().all()
        
        # Group retrieve entities
        tables = set()
        columns = []
        
        for item in similar_items:
            if item.entity_type == "table":
                tables.add(item.entity_name)
            elif item.entity_type == "column":
                table_name = item.entity_name.split(".")[0]
                tables.add(table_name)
                columns.append(item.entity_name)
                
        # Fetch actual metadata for these matched tables
        tables_list = list(tables)
        if not tables_list:
            return {"tables": {}, "relationships": []}
            
        metadata_result = await db.execute(
            select(SchemaMetadata)
            .where(SchemaMetadata.data_source_id == data_source_id, SchemaMetadata.table_name.in_(tables_list))
        )
        metadata_fields = metadata_result.scalars().all()
        
        # Fetch relationships between these tables
        rel_result = await db.execute(
            select(SchemaRelationship)
            .where(
                SchemaRelationship.data_source_id == data_source_id,
                SchemaRelationship.source_table.in_(tables_list) | SchemaRelationship.target_table.in_(tables_list)
            )
        )
        relationships = rel_result.scalars().all()
        
        # Format the context
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
