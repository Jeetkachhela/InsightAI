from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
import re
import ipaddress
from uuid import UUID
from datetime import datetime
from typing import List, Optional, Any, Dict

# User Schemas
class UserBase(BaseModel):
    email: EmailStr = Field(..., max_length=255)

class UserRegister(UserBase):
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit.")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError("Password must contain at least one special character.")
        return v

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

# --- SSRF Protection Helpers ---
_BLOCKED_HOSTNAMES = frozenset([
    "metadata.google.internal",
    "169.254.169.254",  # AWS/GCP/Azure metadata
    "metadata.internal",
])

def _is_cloud_metadata_ip(host: str) -> bool:
    """Check if host resolves to a cloud metadata IP (SSRF protection)."""
    try:
        addr = ipaddress.ip_address(host)
        # Block cloud metadata addresses (169.254.169.254, link-local, reserved)
        return addr.is_link_local or addr.is_reserved or str(addr) == "169.254.169.254"
    except ValueError:
        return False

# Hostname validation regex: RFC-compliant hostname, localhost, or IPv4/IPv6
_HOSTNAME_RE = re.compile(
    r"^("
    r"localhost"
    r"|(?:(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z]{2,63})"  # hostname
    r"|(?:\d{1,3}\.){3}\d{1,3}"  # IPv4
    r"|(?:\[?[0-9a-fA-F:]+\]?)"  # IPv6
    r")$",
    re.IGNORECASE
)

# Database Connection Schemas
class DatabaseConnectionCreate(BaseModel):
    host: Optional[str] = Field(None, min_length=1, max_length=253)
    port: Optional[int] = Field(None, ge=1, le=65535)
    username: Optional[str] = Field(None, min_length=1, max_length=128)
    password: Optional[str] = Field(None, max_length=256)
    database_name: str = Field(..., min_length=1, max_length=128)
    schema_name: Optional[str] = Field("public", min_length=1, max_length=63)

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Host cannot be empty or whitespace only.")
        if v.lower() in _BLOCKED_HOSTNAMES:
            raise ValueError("Connection to cloud metadata endpoints is not allowed.")
        if _is_cloud_metadata_ip(v):
            raise ValueError("Connection to cloud metadata IP ranges is not allowed.")
        if not _HOSTNAME_RE.match(v):
            raise ValueError("Invalid hostname or IP address format.")
        return v

    @field_validator("username", "database_name", "schema_name")
    @classmethod
    def reject_whitespace_only(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("This field cannot be empty or whitespace only.")
            # Reject control characters and dangerous Unicode
            if re.search(r"[\x00-\x1f\x7f]", v):
                raise ValueError("This field contains invalid control characters.")
        return v

class DatabaseConnectionResponse(BaseModel):
    host: Optional[str]
    port: Optional[int]
    username: Optional[str]
    database_name: str
    schema_name: str
    
    model_config = ConfigDict(from_attributes=True)

# Data Source Schemas
class DataSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., max_length=50)  # postgresql, mysql, sqlite
    description: Optional[str] = Field(None, max_length=1000)
    connection_details: DatabaseConnectionCreate

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Data source name cannot be empty or whitespace only.")
        if re.search(r"[\x00-\x1f\x7f]", v):
            raise ValueError("Name contains invalid control characters.")
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"postgresql", "mysql", "sqlite"}
        if v.lower() not in allowed:
            raise ValueError(f"Database type must be one of: {', '.join(sorted(allowed))}")
        return v.lower()

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
    explanation: str

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
