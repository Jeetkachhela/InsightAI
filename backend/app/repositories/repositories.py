from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import List, Optional, Any
from app.models.models import User, DataSource, DatabaseConnection, SchemaMetadata, SchemaRelationship, SchemaEmbedding, Conversation, Message, QueryLog, AuditLog

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self.db.add(user)
        await self.db.flush()
        return user

class DataSourceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, ds_id: UUID, user_id: UUID) -> Optional[DataSource]:
        result = await self.db.execute(
            select(DataSource)
            .options(selectinload(DataSource.connection))
            .where(DataSource.id == ds_id, DataSource.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: UUID) -> List[DataSource]:
        result = await self.db.execute(
            select(DataSource)
            .options(selectinload(DataSource.connection))
            .where(DataSource.user_id == user_id)
        )
        return list(result.scalars().all())

    async def create(self, ds: DataSource) -> DataSource:
        self.db.add(ds)
        await self.db.flush()
        return ds

    async def delete(self, ds: DataSource) -> None:
        await self.db.delete(ds)
        await self.db.flush()

    # Schema Metadata methods
    async def save_metadata(self, metadata_fields: List[SchemaMetadata]) -> None:
        for field in metadata_fields:
            self.db.add(field)
        await self.db.flush()

    async def clear_metadata(self, ds_id: UUID) -> None:
        result = await self.db.execute(select(SchemaMetadata).where(SchemaMetadata.data_source_id == ds_id))
        fields = result.scalars().all()
        for field in fields:
            await self.db.delete(field)
        await self.db.flush()

    async def save_relationships(self, relationships: List[SchemaRelationship]) -> None:
        for rel in relationships:
            self.db.add(rel)
        await self.db.flush()

    async def clear_relationships(self, ds_id: UUID) -> None:
        result = await self.db.execute(select(SchemaRelationship).where(SchemaRelationship.data_source_id == ds_id))
        rels = result.scalars().all()
        for rel in rels:
            await self.db.delete(rel)
        await self.db.flush()

    async def get_metadata(self, ds_id: UUID) -> List[SchemaMetadata]:
        result = await self.db.execute(
            select(SchemaMetadata).where(SchemaMetadata.data_source_id == ds_id)
        )
        return list(result.scalars().all())

    async def get_relationships(self, ds_id: UUID) -> List[SchemaRelationship]:
        result = await self.db.execute(
            select(SchemaRelationship).where(SchemaRelationship.data_source_id == ds_id)
        )
        return list(result.scalars().all())

    # Embeddings methods
    async def save_embeddings(self, embeddings: List[SchemaEmbedding]) -> None:
        for emb in embeddings:
            self.db.add(emb)
        await self.db.flush()

    async def clear_embeddings(self, ds_id: UUID) -> None:
        result = await self.db.execute(select(SchemaEmbedding).where(SchemaEmbedding.data_source_id == ds_id))
        embs = result.scalars().all()
        for emb in embs:
            await self.db.delete(emb)
        await self.db.flush()

    async def search_embeddings(self, ds_id: UUID, query_vector: List[float], limit: int = 10) -> List[SchemaEmbedding]:
        # Using pgvector distance operator '<=>' for cosine distance in SQLAlchemy
        # Cosine similarity is 1 - Cosine distance.
        # Order by distance (ascending) to get most similar
        result = await self.db.execute(
            select(SchemaEmbedding)
            .where(SchemaEmbedding.data_source_id == ds_id)
            .order_by(SchemaEmbedding.embedding.cosine_distance(query_vector))
            .limit(limit)
        )
        return list(result.scalars().all())

class ConversationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, conv_id: UUID, user_id: UUID) -> Optional[Conversation]:
        result = await self.db.execute(
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(Conversation.id == conv_id, Conversation.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: UUID) -> List[Conversation]:
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(self, conv: Conversation) -> Conversation:
        self.db.add(conv)
        await self.db.flush()
        return conv

    async def add_message(self, message: Message) -> Message:
        self.db.add(message)
        await self.db.flush()
        return message

class QueryLogRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(self, ql: QueryLog) -> QueryLog:
        self.db.add(ql)
        await self.db.flush()
        return ql

    async def list_by_user(self, user_id: UUID, limit: int = 50) -> List[QueryLog]:
        result = await self.db.execute(
            select(QueryLog)
            .where(QueryLog.user_id == user_id)
            .order_by(QueryLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

class AuditLogRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(self, al: AuditLog) -> AuditLog:
        self.db.add(al)
        await self.db.flush()
        return al
