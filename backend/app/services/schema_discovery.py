import sqlite3
from typing import List, Dict, Any, Tuple
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine
from app.models.models import SchemaMetadata, SchemaRelationship
from app.core.security import decrypt_credential
from app.core.logging import logger

class SchemaDiscoveryService:
    @staticmethod
    def _get_connection_string(conn_details: Dict[str, Any], db_type: str) -> str:
        """
        Reconstructs the connection string from encrypted connection details.
        Uses urllib.parse.quote_plus to safely encode credentials (SEC-015).
        """
        if db_type == "sqlite":
            return f"sqlite:///{conn_details['database_name']}"
            
        # Decrypt password
        password = ""
        if conn_details.get("password_encrypted"):
            password = decrypt_credential(conn_details["password_encrypted"])
            
        username = quote_plus(conn_details.get("username", ""))
        host = conn_details.get("host", "localhost")
        port = conn_details.get("port", 5432)
        db_name = conn_details["database_name"]
        
        ssl_suffix = ""
        if "?" not in db_name and any(cloud_domain in host.lower() for cloud_domain in [".neon.tech", ".rds.amazonaws.com", ".supabase.co", ".render.com", ".elephantsql.com"]):
            ssl_suffix = "?sslmode=require"
        
        if password:
            return f"postgresql://{username}:{quote_plus(password)}@{host}:{port}/{db_name}{ssl_suffix}"
        return f"postgresql://{username}@{host}:{port}/{db_name}{ssl_suffix}"

    async def discover_schema(self, conn_details: Dict[str, Any], db_type: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Connects to the database and extracts columns, data types, primary/foreign keys, and relationships.
        Returns: (columns_list, relationships_list)
        """
        conn_str = self._get_connection_string(conn_details, db_type)
        
        # Check database type
        if db_type == "sqlite":
            return self._discover_sqlite(conn_str)
        else:
            return await self._discover_postgresql(conn_str, conn_details.get("schema_name", "public"))

    def _discover_sqlite(self, conn_str: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        logger.info(f"Starting SQLite schema discovery for path: {conn_str}")
        db_path = conn_str.replace("sqlite:///", "")
        
        columns_out = []
        relationships_out = []
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 1. Get tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = [row[0] for row in cursor.fetchall()]
            
            for table in tables:
                # 2. Get table info (columns, types, nullability, primary key)
                cursor.execute(f"PRAGMA table_info({table});")
                # columns returned: cid, name, type, notnull, dflt_value, pk
                pragma_cols = cursor.fetchall()
                
                # 3. Get foreign keys
                cursor.execute(f"PRAGMA foreign_key_list({table});")
                # foreign keys returned: id, seq, table, from, to, on_update, on_delete, match
                pragma_fks = cursor.fetchall()
                fk_source_cols = {fk[3] for fk in pragma_fks}
                
                # Parse columns
                for col in pragma_cols:
                    col_name = col[1]
                    col_type = col[2]
                    is_nullable = col[3] == 0
                    is_pk = col[5] > 0
                    is_fk = col_name in fk_source_cols
                    
                    columns_out.append({
                        "table_name": table,
                        "column_name": col_name,
                        "data_type": col_type,
                        "is_nullable": is_nullable,
                        "is_primary_key": is_pk,
                        "is_foreign_key": is_fk,
                        "description": f"Column {col_name} in table {table}"
                    })
                    
                # Parse relationships
                for fk in pragma_fks:
                    relationships_out.append({
                        "source_table": table,
                        "source_column": fk[3],
                        "target_table": fk[2],
                        "target_column": fk[4]
                    })
            
            conn.close()
            return columns_out, relationships_out
            
        except Exception as e:
            logger.error(f"SQLite discovery failed: {e}")
            raise e

    async def _discover_postgresql(self, conn_str: str, schema_name: str = "public") -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        logger.info(f"Starting PostgreSQL schema discovery for: {conn_str.split('@')[-1]}")
        
        columns_out = []
        relationships_out = []
        
        # We can run sync discovery using a temporary engine to simplify the connection
        # because async dynamic driver generation is more complex and schema discovery is a backend admin task.
        engine = None
        try:
            engine = create_engine(
                conn_str,
                connect_args={"connect_timeout": 10},
                pool_timeout=10,
                pool_pre_ping=True
            )
            with engine.connect() as conn:
                # 1. Query columns
                col_query = text("""
                    SELECT 
                        c.table_name, 
                        c.column_name, 
                        c.data_type, 
                        c.is_nullable,
                        (SELECT COUNT(*) FROM information_schema.table_constraints tc
                         JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
                         WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = c.table_schema AND tc.table_name = c.table_name AND kcu.column_name = c.column_name) > 0 AS is_primary_key,
                        (SELECT COUNT(*) FROM information_schema.table_constraints tc
                         JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
                         WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = c.table_schema AND tc.table_name = c.table_name AND kcu.column_name = c.column_name) > 0 AS is_foreign_key
                    FROM information_schema.columns c
                    JOIN information_schema.tables t ON c.table_name = t.table_name AND c.table_schema = t.table_schema
                    WHERE c.table_schema = :schema AND t.table_type = 'BASE TABLE'
                    ORDER BY c.table_name, c.ordinal_position;
                """)
                
                res = conn.execute(col_query, {"schema": schema_name})
                for row in res.fetchall():
                    columns_out.append({
                        "table_name": row[0],
                        "column_name": row[1],
                        "data_type": row[2],
                        "is_nullable": row[3] == "YES",
                        "is_primary_key": row[4],
                        "is_foreign_key": row[5],
                        "description": f"Column {row[1]} in table {row[0]}"
                    })
                    
                # 2. Query relationships
                rel_query = text("""
                    SELECT
                        kcu.table_name AS source_table,
                        kcu.column_name AS source_column,
                        ccu.table_name AS target_table,
                        ccu.column_name AS target_column
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = :schema;
                """)
                
                res = conn.execute(rel_query, {"schema": schema_name})
                for row in res.fetchall():
                    relationships_out.append({
                        "source_table": row[0],
                        "source_column": row[1],
                        "target_table": row[2],
                        "target_column": row[3]
                    })
                    
            return columns_out, relationships_out
            
        except Exception as e:
            logger.error(f"PostgreSQL discovery failed: {e}")
            raise e
        finally:
            if engine:
                engine.dispose()
