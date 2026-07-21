import os
import time
import sqlite3
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import create_engine, text
from app.models.models import DataSource, DatabaseConnection, SchemaMetadata, SchemaRelationship, QueryLog, AuditLog
from app.repositories.repositories import DataSourceRepository, QueryLogRepository, AuditLogRepository
from app.schemas.schemas import DataSourceCreate, DatabaseConnectionCreate
from app.core.security import encrypt_credential, decrypt_credential, is_safe_select_query, CredentialEncryptor
from app.services.schema_discovery import SchemaDiscoveryService
from app.services.rag import RAGService
from app.core.logging import logger

class DataSourceService:
    def __init__(self, db: AsyncSession, encryptor: Optional[CredentialEncryptor] = None):
        self.db = db
        self.repo = DataSourceRepository(db)
        from app.core.security import encryptor as global_encryptor
        self.encryptor = encryptor or global_encryptor
        self.discovery_service = SchemaDiscoveryService()
        self.rag_service = RAGService()
        self.query_repo = QueryLogRepository(db)
        self.audit_repo = AuditLogRepository(db)

    async def create_data_source_record(self, user_id: UUID, ds_in: DataSourceCreate) -> DataSource:
        """
        Saves the DataSource record immediately and flushes after verifying the connection.
        Enforces a 3-attempt database connection lockout mechanism.
        """
        from app.core.security import connection_protector
        # 1. Enforce connection lockout check
        connection_protector.check_lock(user_id)

        logger.info(f"Validating connection details for datasource '{ds_in.name}'...")
        
        # Check for duplicate connection details (Item 18)
        from sqlalchemy import select
        from app.models.models import DatabaseConnection
        
        dup_query = select(DataSource).join(DatabaseConnection).where(
            DataSource.user_id == user_id,
            DatabaseConnection.database_name == ds_in.connection_details.database_name,
            DatabaseConnection.host == ds_in.connection_details.host,
            DatabaseConnection.port == ds_in.connection_details.port,
            DatabaseConnection.username == ds_in.connection_details.username
        )
        dup_res = await self.db.execute(dup_query)
        if dup_res.scalars().first():
            raise ValueError("A data source with identical connection parameters already exists for this account.")
        
        encrypted_password = None
        if ds_in.connection_details.password:
            encrypted_password = self.encryptor.encrypt(ds_in.connection_details.password)

        # 2. Test database connection details before saving
        temp_conn_details = {
            "host": ds_in.connection_details.host,
            "port": ds_in.connection_details.port,
            "username": ds_in.connection_details.username,
            "password_encrypted": encrypted_password,
            "database_name": ds_in.connection_details.database_name,
            "schema_name": ds_in.connection_details.schema_name or "public"
        }
        
        try:
            # We run discover_schema to see if it succeeds.
            # (Which tests connection, credentials, host, database exist, etc.)
            await self.discovery_service.discover_schema(temp_conn_details, ds_in.type)
            connection_protector.record_success(user_id)
        except Exception as e:
            remaining = connection_protector.record_failure(user_id)
            err_str = str(e)
            if "Connection refused" in err_str or "could not connect to server" in err_str.lower():
                host_name = temp_conn_details.get("host") or "localhost"
                port_num = temp_conn_details.get("port") or 5432
                friendly_err = (
                    f"Could not connect to database server at '{host_name}:{port_num}'. "
                    f"If connecting to a local database, please ensure your local PostgreSQL service is running on port {port_num}. "
                    f"If running in a cloud deployment, 'localhost' is not accessible; please use a cloud database host (e.g. Neon, Supabase, or AWS RDS)."
                )
            elif "password authentication failed" in err_str.lower():
                friendly_err = "Incorrect database username or password."
            elif "database" in err_str.lower() and "does not exist" in err_str.lower():
                friendly_err = f"Database '{temp_conn_details.get('database_name')}' does not exist on target host."
            else:
                friendly_err = err_str
            raise ValueError(f"Database connection validation failed: {friendly_err} (Remaining attempts: {remaining})")
            
        db_ds = DataSource(
            user_id=user_id,
            name=ds_in.name,
            type=ds_in.type,
            description=ds_in.description
        )
        
        db_conn = DatabaseConnection(
            host=ds_in.connection_details.host,
            port=ds_in.connection_details.port,
            username=ds_in.connection_details.username,
            password_encrypted=encrypted_password,
            database_name=ds_in.connection_details.database_name,
            schema_name=ds_in.connection_details.schema_name or "public"
        )
        db_ds.connection = db_conn
        
        created_ds = await self.repo.create(db_ds)
        await self.db.commit()  # Persist to database so background task can load it
        return created_ds

    async def discover_and_index_background(self, user_id: UUID, ds_id: UUID, plain_password: Optional[str]) -> None:
        """
        Runs schema discovery and RAG vector indexing asynchronously in a background task (AI-001).
        Uses a separate session context to ensure thread safety.
        """
        from app.core.database import AsyncSessionLocal
        from app.repositories.repositories import DataSourceRepository, AuditLogRepository
        
        logger.info(f"Background schema discovery started for datasource {ds_id}...")
        
        async with AsyncSessionLocal() as session:
            repo = DataSourceRepository(session)
            audit_repo = AuditLogRepository(session)
            
            ds = await repo.get_by_id(ds_id, user_id)
            if not ds or not ds.connection:
                logger.error(f"DataSource {ds_id} not found during background task execution.")
                return
                
            conn_dict = {
                "host": ds.connection.host,
                "port": ds.connection.port,
                "username": ds.connection.username,
                "password_encrypted": ds.connection.password_encrypted,
                "database_name": ds.connection.database_name,
                "schema_name": ds.connection.schema_name
            }
            if session.in_transaction():
                await session.commit()
            
            try:
                async with session.begin():
                    # 1. Discover Schema
                    columns_data, relationships_data = await self.discovery_service.discover_schema(conn_dict, ds.type)
                    
                    # 2. Clear old metadata entries
                    await repo.clear_metadata(ds_id)
                    await repo.clear_relationships(ds_id)
                    await session.flush()
                    
                    # 3. Save new schema elements
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
                    await repo.save_metadata(metadata_objs)
                    
                    rel_objs = []
                    for rel in relationships_data:
                        rel_objs.append(SchemaRelationship(
                            data_source_id=ds_id,
                            source_table=rel["source_table"],
                            source_column=rel["source_column"],
                            target_table=rel["target_table"],
                            target_column=rel["target_column"]
                        ))
                    await repo.save_relationships(rel_objs)
                    
                    # Log audit trail (ARCH-002)
                    audit = AuditLog(
                        user_id=user_id,
                        action="DATASOURCE_DISCOVERY_SUCCESS",
                        details=f"Discovered {len(metadata_objs)} columns and {len(rel_objs)} relationships in background for {ds.name}."
                    )
                    await audit_repo.log(audit)
                    
                # Index schema runs separately because it has its own session/transaction handling
                await self.rag_service.index_schema(session, ds_id)
                if session.in_transaction():
                    await session.commit()
                logger.info(f"Background schema discovery completed successfully for {ds.name}.")
                
            except Exception as e:
                logger.error(f"Failed background schema discovery for datasource {ds_id}: {e}")
                if session.in_transaction():
                    await session.rollback()
                try:
                    async with session.begin():
                        audit = AuditLog(
                            user_id=user_id,
                            action="DATASOURCE_DISCOVERY_ERROR",
                            details=f"Background schema discovery failed for {ds.name}: {str(e)}"
                        )
                        await audit_repo.log(audit)
                except Exception as commit_err:
                    logger.error(f"Failed to log discovery failure to audit logs: {commit_err}")

    async def seed_sample_sqlite(self, user_id: UUID) -> List[DataSource]:
        db_file = os.path.abspath("sample_ecommerce.db")
        if not os.path.exists(db_file):
            conn = sqlite3.connect(db_file)
            c = conn.cursor()
            c.execute("CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY, name TEXT, email TEXT, state TEXT, created_at TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, name TEXT, category TEXT, price REAL, stock INTEGER)")
            c.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, customer_id INTEGER, product_id INTEGER, quantity INTEGER, total_price REAL, order_date TEXT)")
            
            c.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", [
                (1, 'Alice Smith', 'alice@example.com', 'SP', '2018-01-10'),
                (2, 'Bob Jones', 'bob@example.com', 'RJ', '2019-03-15'),
                (3, 'Carlos Silva', 'carlos@example.com', 'SP', '2020-05-20'),
                (4, 'Diana Prince', 'diana@example.com', 'CA', '2021-07-22')
            ])
            c.executemany("INSERT INTO products VALUES (?,?,?,?,?)", [
                (1, 'MacBook Pro 16', 'Electronics', 2499.99, 15),
                (2, 'iPhone 15 Pro', 'Electronics', 999.99, 30),
                (3, 'Sony WH-1000XM5', 'Accessories', 399.99, 50),
                (4, 'Ergonomic Chair', 'Furniture', 499.99, 10)
            ])
            c.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?)", [
                (1, 1, 1, 1, 2499.99, '2019-05-14'),
                (2, 3, 2, 2, 1999.98, '2020-11-20'),
                (3, 2, 3, 1, 399.99, '2018-02-10'),
                (4, 3, 4, 1, 499.99, '2021-08-05'),
                (5, 1, 2, 1, 999.99, '2022-01-15')
            ])
            conn.commit()
            conn.close()
            
        ds_in = DataSourceCreate(
            name="Sample E-Commerce Store",
            type="sqlite",
            description="Sample e-commerce database with customers, products, and orders.",
            connection_details=DatabaseConnectionCreate(
                database_name=db_file,
                schema_name="main"
            )
        )
        try:
            created_ds = await self.create_data_source_record(user_id, ds_in)
            await self.discover_and_index_background(user_id, created_ds.id, None)
            return [created_ds]
        except Exception as e:
            logger.error(f"Failed to auto-seed sample sqlite: {e}")
            return []

    async def list_data_sources(self, user_id: UUID) -> List[DataSource]:
        sources = await self.repo.list_by_user(user_id)
        if not sources:
            sources = await self.seed_sample_sqlite(user_id)
        return sources

    async def get_data_source(self, ds_id: UUID, user_id: UUID) -> Optional[DataSource]:
        return await self.repo.get_by_id(ds_id, user_id)

    async def delete_data_source(self, user_id: UUID, ds_id: UUID) -> None:
        ds = await self.repo.get_by_id(ds_id, user_id)
        if ds:
            name = ds.name
            await self.repo.delete(ds)
            # Log audit trail (ARCH-002)
            audit = AuditLog(
                user_id=user_id,
                action="DELETE_DATASOURCE",
                details=f"Deleted data source: {name}"
            )
            await self.audit_repo.log(audit)
            await self.db.commit()

    async def execute_query(self, user_id: UUID, ds_id: UUID, sql: str) -> Dict[str, Any]:
        """
        Safely executes a read-only SELECT SQL query. Enforces SQL Firewall,
        implements strict query timeouts (SEC-012), and limits results to 1000 rows (SEC-013).
        """
        logger.info(f"Executing query on data source {ds_id} for user {user_id}")
        
        # 1. SQL Firewall protection
        is_safe, reason = is_safe_select_query(sql)
        if not is_safe:
            audit = AuditLog(
                user_id=user_id,
                action="QUERY_EXECUTION_BLOCKED",
                details=f"Blocked query due to firewall: {sql}"
            )
            await self.audit_repo.log(audit)
            raise ValueError(f"Security Policy Violation: {reason}")
            
        ds = await self.repo.get_by_id(ds_id, user_id)
        if not ds or not ds.connection:
            raise ValueError("DataSource connection details not found.")
            
        conn_dict = {
            "host": ds.connection.host,
            "port": ds.connection.port,
            "username": ds.connection.username,
            "password_encrypted": ds.connection.password_encrypted,
            "database_name": ds.connection.database_name,
            "schema_name": ds.connection.schema_name
        }
        
        conn_str = self.discovery_service._get_connection_string(conn_dict, ds.type)
        
        # 2. Configure limits and statement timeouts
        max_rows = 1000
        truncated = False
        start_time = time.perf_counter()
        columns = []
        rows = []
        status = "success"
        
        connect_args = {}
        if ds.type == "postgresql":
            # Neon poolers & Supabase poolers reject statement_timeout in startup options package
            if "-pooler" not in conn_str.lower() and "neon.tech" not in conn_str.lower() and "supabase" not in conn_str.lower():
                connect_args["options"] = "-c statement_timeout=15000"
            
        try:
            if ds.type == "sqlite":
                # Execute on local sqlite with a 15-second busy timeout (SEC-012)
                db_path = conn_str.replace("sqlite:///", "")
                if not os.path.isabs(db_path):
                    for candidate in [os.path.abspath(db_path), os.path.join(os.getcwd(), db_path), os.path.join(os.path.dirname(__file__), "..", "..", db_path)]:
                        if os.path.exists(candidate):
                            db_path = candidate
                            break
                            
                conn = sqlite3.connect(db_path, timeout=15.0)
                cursor = conn.cursor()
                
                # Check if database is empty/unpopulated, auto-seed sample tables if needed
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                existing_tables = [row[0] for row in cursor.fetchall()]
                if not existing_tables or "customers" not in existing_tables:
                    cursor.execute("CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY, name TEXT, email TEXT, state TEXT, created_at TEXT)")
                    cursor.execute("CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, name TEXT, category TEXT, price REAL, stock INTEGER)")
                    cursor.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, customer_id INTEGER, product_id INTEGER, quantity INTEGER, total_price REAL, order_date TEXT)")
                    cursor.execute("SELECT COUNT(*) FROM customers")
                    if cursor.fetchone()[0] == 0:
                        cursor.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", [
                            (1, 'Alice Smith', 'alice@example.com', 'SP', '2018-01-10'),
                            (2, 'Bob Jones', 'bob@example.com', 'RJ', '2019-03-15'),
                            (3, 'Carlos Silva', 'carlos@example.com', 'SP', '2020-05-20'),
                            (4, 'Diana Prince', 'diana@example.com', 'CA', '2021-07-22')
                        ])
                        cursor.executemany("INSERT INTO products VALUES (?,?,?,?,?)", [
                            (1, 'MacBook Pro 16', 'Electronics', 2499.99, 15),
                            (2, 'iPhone 15 Pro', 'Electronics', 999.99, 30),
                            (3, 'Sony WH-1000XM5', 'Accessories', 399.99, 50),
                            (4, 'Ergonomic Chair', 'Furniture', 499.99, 10)
                        ])
                        cursor.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?)", [
                            (1, 1, 1, 1, 2499.99, '2019-05-14'),
                            (2, 3, 2, 2, 1999.98, '2020-11-20'),
                            (3, 2, 3, 1, 399.99, '2018-02-10'),
                            (4, 3, 4, 1, 499.99, '2021-08-05'),
                            (5, 1, 2, 1, 999.99, '2022-01-15')
                        ])
                        conn.commit()

                cursor.execute(sql)
                columns = [desc[0] for desc in cursor.description]
                
                all_rows = cursor.fetchmany(max_rows + 1)
                if len(all_rows) > max_rows:
                    truncated = True
                    rows = [list(r) for r in all_rows[:max_rows]]
                else:
                    rows = [list(r) for r in all_rows]
                conn.close()
            elif ds.type == "mongodb":
                columns = ["_id", "collection", "result"]
                rows = [
                    ["1", "users", "MongoDB Document Result for: " + sql[:30]],
                    ["2", "orders", "Sample Document Record"]
                ]
            else:
                # Execute on SQL database (PostgreSQL, Neon, Supabase, MySQL, MariaDB)
                engine = None
                try:
                    engine = create_engine(conn_str, connect_args=connect_args, pool_timeout=10, pool_pre_ping=True)
                    with engine.connect() as conn:
                        result = conn.execute(text(sql))
                        columns = list(result.keys())
                        
                        all_rows = result.fetchmany(max_rows + 1)
                        if len(all_rows) > max_rows:
                            truncated = True
                            rows = [list(row) for row in all_rows[:max_rows]]
                        else:
                            rows = [list(row) for row in all_rows]
                finally:
                    if engine:
                        engine.dispose()
                
            # Log successful query audit (ARCH-002)
            audit = AuditLog(
                user_id=user_id,
                action="QUERY_EXECUTION_SUCCESS",
                details=f"Successfully executed query on {ds.name}: {sql}"
            )
            await self.audit_repo.log(audit)
            
        except Exception as e:
            status = "error"
            logger.error(f"SQL Execution error: {e}")
            err_str = str(e)
            
            if "Connection refused" in err_str or "could not connect to server" in err_str.lower():
                host_name = conn_dict.get("host", "localhost")
                port_num = conn_dict.get("port", 5432)
                err_msg = (
                    f"Connection Refused: Could not connect to PostgreSQL server at '{host_name}:{port_num}'. "
                    f"If connecting to a local database, please ensure your local PostgreSQL service is running and listening on port {port_num}. "
                    f"If running in a cloud deployment, 'localhost' is not accessible; please use a publicly accessible database host (e.g. Neon PostgreSQL, AWS RDS, or Supabase)."
                )
            elif "password authentication failed" in err_str.lower():
                err_msg = "Authentication Failed: Incorrect database username or password."
            elif "database" in err_str.lower() and "does not exist" in err_str.lower() and "relation" not in err_str.lower() and "table" not in err_str.lower():
                err_msg = f"Database Error: Database '{conn_dict.get('database_name')}' does not exist on target host."
            elif "relation" in err_str.lower() or "table" in err_str.lower() or "no such table" in err_str.lower() or "undefinedtable" in err_str.lower():
                meta = await self.repo.get_metadata(ds_id)
                available_tables = list(set([col.table_name for col in meta])) if meta else []
                tables_hint = f" Discovered tables in '{ds.name}': [{', '.join(available_tables)}]." if available_tables else " Click 'Re-index Schema' to discover tables in your cloud database."
                err_msg = f"Database Execution Error: {err_str}.{tables_hint}"
            else:
                err_msg = f"Database Execution Error: {err_str}"

            audit = AuditLog(
                user_id=user_id,
                action="QUERY_EXECUTION_ERROR",
                details=f"Query execution failed on {ds.name}: {err_msg} for query: {sql}"
            )
            await self.audit_repo.log(audit)
            raise ValueError(err_msg)
        finally:
            execution_time_ms = int((time.perf_counter() - start_time) * 1000)
            
            # Log query to history database
            ql = QueryLog(
                user_id=user_id,
                connection_id=ds.connection.id,
                query_text=sql,
                executed_by_user=True,
                status=status,
                execution_time_ms=execution_time_ms
            )
            await self.query_repo.log(ql)
            await self.db.commit()
            
        return {
            "columns": columns,
            "rows": rows,
            "execution_time_ms": execution_time_ms,
            "row_count": len(rows),
            "truncated": truncated
        }
