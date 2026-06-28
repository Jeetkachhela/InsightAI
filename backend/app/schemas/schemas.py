from pydantic import BaseModel, EmailStr, Field, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import List, Optional, Any, Dict

# User Schemas
class UserBase(BaseModel):
    email: EmailStr = Field(..., max_length=255)

class UserRegister(UserBase):
    password: str = Field(..., min_length=6, max_length=128)

class UserLogin(UserBase):
    password: str = Field(..., max_length=128)

class UserResponse(UserBase):
    id: UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
    user_id: Optional[UUID] = None

# Database Connection Schemas
class DatabaseConnectionCreate(BaseModel):
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database_name: str
    schema_name: Optional[str] = "public"

class DatabaseConnectionResponse(BaseModel):
    host: Optional[str]
    port: Optional[int]
    username: Optional[str]
    database_name: str
    schema_name: str
    
    model_config = ConfigDict(from_attributes=True)

# Data Source Schemas
class DataSourceCreate(BaseModel):
    name: str = Field(..., max_length=100)
    type: str = Field(..., max_length=50)  # postgresql, mysql, sqlite
    description: Optional[str] = Field(None, max_length=1000)
    connection_details: DatabaseConnectionCreate

class DataSourceResponse(BaseModel):
    id: UUID
    name: str
    type: str
    description: Optional[str]
    created_at: datetime
    connection: Optional[DatabaseConnectionResponse] = None
    
    model_config = ConfigDict(from_attributes=True)

# Metadata & Relationship Schemas
class SchemaMetadataResponse(BaseModel):
    table_name: str
    column_name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool
    is_foreign_key: bool
    description: Optional[str]
    
    model_config = ConfigDict(from_attributes=True)

class SchemaRelationshipResponse(BaseModel):
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    
    model_config = ConfigDict(from_attributes=True)

# Conversation & Message Schemas
class MessageCreate(BaseModel):
    content: str = Field(..., max_length=4000)

class MessageResponse(BaseModel):
    id: UUID
    sender: str
    content: str
    step_details: Optional[Dict[str, Any]] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ConversationCreate(BaseModel):
    title: str = Field(..., max_length=255)

class ConversationResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    messages: List[MessageResponse] = []
    
    model_config = ConfigDict(from_attributes=True)

# SQL Workflow Schemas
class QueryRequest(BaseModel):
    nl_query: str = Field(..., max_length=4000)
    data_source_id: UUID
    conversation_id: Optional[UUID] = None

class SQLResponse(BaseModel):
    query_plan: Dict[str, Any]
    generated_sql: str
    confidence_score: float
    impact_analysis: Dict[str, Any]
    validation: Dict[str, Any]
    conversation_id: UUID
    message_id: UUID

class SQLActionRequest(BaseModel):
    sql: str = Field(..., max_length=8000)
    data_source_id: UUID

class SQLActionResponse(BaseModel):
    is_safe: bool
    result: str

class SQLExplainResponse(BaseModel):
    explanation: str

class SQLOptimizeResponse(BaseModel):
    original_sql: str
    optimized_sql: str
    performance_analysis: str
    recommendations: List[str]

class SQLDebugResponse(BaseModel):
    original_sql: str
    corrected_sql: str
    error_detected: str
    explanation: str

class SQLExecuteRequest(BaseModel):
    sql: str = Field(..., max_length=8000)
    data_source_id: UUID

class SQLExecuteResponse(BaseModel):
    columns: List[str]
    rows: List[List[Any]]
    execution_time_ms: int
    row_count: int

# System Schemas
class HealthCheckResponse(BaseModel):
    status: str
    timestamp: datetime
    database: str
    groq: str


class UserSessionResponse(BaseModel):
    id: UUID
    ip_address: Optional[str]
    user_agent: Optional[str]
    is_active: bool
    created_at: datetime
    expires_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
