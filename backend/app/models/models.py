import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import relationship
from app.core.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    data_sources = relationship("DataSource", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    query_logs = relationship("QueryLog", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")

class DataSource(Base):
    __tablename__ = "data_sources"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String(50), nullable=False)  # postgresql, sqlite, mysql etc
    description = Column(Text, nullable=True)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __mapper_args__ = {
        "version_id_col": version
    }
    
    user = relationship("User", back_populates="data_sources")
    connection = relationship("DatabaseConnection", back_populates="data_source", uselist=False, cascade="all, delete-orphan")
    metadata_fields = relationship("SchemaMetadata", back_populates="data_source", cascade="all, delete-orphan")
    relationships = relationship("SchemaRelationship", back_populates="data_source", cascade="all, delete-orphan")
    embeddings = relationship("SchemaEmbedding", back_populates="data_source", cascade="all, delete-orphan")

class DatabaseConnection(Base):
    __tablename__ = "database_connections"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_source_id = Column(UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    host = Column(String(255), nullable=True)  # Nullable for sqlite
    port = Column(Integer, nullable=True)      # Nullable for sqlite
    username = Column(String(255), nullable=True)
    password_encrypted = Column(Text, nullable=True)
    database_name = Column(String(255), nullable=False)
    schema_name = Column(String(255), default="public", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    data_source = relationship("DataSource", back_populates="connection")

class SchemaMetadata(Base):
    __tablename__ = "schema_metadata"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_source_id = Column(UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    table_name = Column(String(255), nullable=False, index=True)
    column_name = Column(String(255), nullable=False)
    data_type = Column(String(100), nullable=False)
    is_nullable = Column(Boolean, default=True, nullable=False)
    is_primary_key = Column(Boolean, default=False, nullable=False)
    is_foreign_key = Column(Boolean, default=False, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    data_source = relationship("DataSource", back_populates="metadata_fields")

class SchemaRelationship(Base):
    __tablename__ = "schema_relationships"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_source_id = Column(UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    source_table = Column(String(255), nullable=False)
    source_column = Column(String(255), nullable=False)
    target_table = Column(String(255), nullable=False)
    target_column = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    data_source = relationship("DataSource", back_populates="relationships")

class SchemaEmbedding(Base):
    __tablename__ = "schema_embeddings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_source_id = Column(UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)  # table or column
    entity_name = Column(String(255), nullable=False)  # table_name or table_name.column_name
    description = Column(Text, nullable=False)
    fingerprint = Column(String(64), nullable=True, index=True)
    # Llama embeddings or sentence-transformers all-MiniLM-L6-v2 embeddings (384 dimensions)
    embedding = Column(Vector(384), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    data_source = relationship("DataSource", back_populates="embeddings")

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __mapper_args__ = {
        "version_id_col": version
    }
    
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender = Column(String(50), nullable=False)  # user or assistant
    content = Column(Text, nullable=False)
    step_details = Column(JSON, nullable=True)  # Detailed workflow stage JSON
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    conversation = relationship("Conversation", back_populates="messages")

class QueryLog(Base):
    __tablename__ = "query_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    connection_id = Column(UUID(as_uuid=True), ForeignKey("database_connections.id", ondelete="SET NULL"), nullable=True, index=True)
    query_text = Column(Text, nullable=False)
    executed_by_user = Column(Boolean, default=False, nullable=False)
    status = Column(String(50), nullable=False)  # success or error
    execution_time_ms = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    user = relationship("User", back_populates="query_logs")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    details = Column(Text, nullable=False)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    user = relationship("User", back_populates="audit_logs")


class UserSession(Base):
    __tablename__ = "user_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    refresh_token_hash = Column(String(255), nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    
    user = relationship("User", back_populates="sessions")
