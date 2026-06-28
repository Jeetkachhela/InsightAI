import os
import csv
import asyncio
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Set environment paths and load .env
os.environ["PYTHONPATH"] = os.path.dirname(os.path.abspath(__file__))
from app.core.config import settings
from app.core.database import Base
from app.core.security import hash_password, encrypt_credential
from app.models.models import User, DataSource, DatabaseConnection, SchemaMetadata, SchemaRelationship
from app.services.schema_discovery import SchemaDiscoveryService
from app.services.rag import RAGService
from app.core.logging import setup_logging, logger

# Configure logging
setup_logging()

CSV_DIR = "D:\\SalesOP\\datasets\\archive1"

# Safe parser for datetimes
def parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return None

async def seed_database():
    logger.info("Initializing seeding process...")
    
    # 1. Initialize SQLAlchemy Engine
    db_url = settings.DATABASE_URL
    connect_args = {"statement_cache_size": 0}
    
    if "postgresql" in db_url or "postgres" in db_url:
        if "sslmode" in db_url:
            db_url = db_url.split("?")[0]
            connect_args["ssl"] = "require"
            
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
        
    async_engine = create_async_engine(db_url, pool_pre_ping=True, connect_args=connect_args)
    AsyncSessionLocal = sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    # 2. Run system table migrations/creations
    async with async_engine.begin() as conn:
        logger.info("Dropping existing conflicting tables to ensure UUID keys...")
        drop_tables = [
            "audit_logs", "query_logs", "messages", "conversations",
            "schema_embeddings", "schema_relationships", "schema_metadata",
            "database_connections", "data_sources", "users",
            "olist_order_reviews", "olist_order_items", "olist_orders",
            "olist_products", "olist_customers"
        ]
        for table in drop_tables:
            try:
                await conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE;"))
            except Exception as e:
                logger.warning(f"Failed to drop table {table}: {e}")

        logger.info("Ensuring pgvector extension and creating app tables...")
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        except Exception as e:
            logger.warning(f"pgvector extension creation warning: {e}")
        await conn.run_sync(Base.metadata.create_all)
        
    # Dispose engine to clear prepared statement cache
    await async_engine.dispose()
    
    # Recreate engine and session local
    async_engine = create_async_engine(db_url, pool_pre_ping=True, connect_args=connect_args)
    AsyncSessionLocal = sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
        
    async with AsyncSessionLocal() as db:
        # 3. Create default user admin@insightforge.ai / password123
        logger.info("Creating default system user...")
        from sqlalchemy.future import select
        res = await db.execute(select(User).where(User.email == "admin@insightforge.ai"))
        user = res.scalar_one_or_none()
        
        if not user:
            user = User(
                email="admin@insightforge.ai",
                password_hash=hash_password("password123")
            )
            db.add(user)
            await db.flush()
            logger.info(f"Default user created with ID: {user.id}")
        else:
            logger.info(f"Default user already exists (ID: {user.id})")
            
        user_id = user.id

        # 4. Create the Olist E-commerce tables
        logger.info("Creating Olist e-commerce database tables in public schema...")
        create_tables_sql = """
        CREATE TABLE IF NOT EXISTS olist_customers (
            customer_id VARCHAR(50) PRIMARY KEY,
            customer_unique_id VARCHAR(50),
            customer_zip_code_prefix INT,
            customer_city VARCHAR(100),
            customer_state VARCHAR(10)
        );

        CREATE TABLE IF NOT EXISTS olist_products (
            product_id VARCHAR(50) PRIMARY KEY,
            product_category_name VARCHAR(100),
            product_name_lenght INT,
            product_description_lenght INT,
            product_photos_qty INT,
            product_weight_g INT,
            product_length_cm INT,
            product_height_cm INT,
            product_width_cm INT
        );

        CREATE TABLE IF NOT EXISTS olist_orders (
            order_id VARCHAR(50) PRIMARY KEY,
            customer_id VARCHAR(50) REFERENCES olist_customers(customer_id),
            order_status VARCHAR(50),
            order_purchase_timestamp TIMESTAMP,
            order_approved_at TIMESTAMP,
            order_delivered_carrier_date TIMESTAMP,
            order_delivered_customer_date TIMESTAMP,
            order_estimated_delivery_date TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS olist_order_items (
            order_id VARCHAR(50) REFERENCES olist_orders(order_id),
            order_item_id INT,
            product_id VARCHAR(50) REFERENCES olist_products(product_id),
            seller_id VARCHAR(50),
            shipping_limit_date TIMESTAMP,
            price DECIMAL(10, 2),
            freight_value DECIMAL(10, 2),
            PRIMARY KEY (order_id, order_item_id)
        );

        CREATE TABLE IF NOT EXISTS olist_order_reviews (
            review_id VARCHAR(50) PRIMARY KEY,
            order_id VARCHAR(50) REFERENCES olist_orders(order_id),
            review_score INT,
            review_comment_title TEXT,
            review_comment_message TEXT,
            review_creation_date TIMESTAMP,
            review_answer_timestamp TIMESTAMP
        );
        """
        # Split and execute statements one by one to avoid multi-command prepared statement error in asyncpg
        async with async_engine.begin() as conn:
            for statement in create_tables_sql.split(";"):
                clean_stmt = statement.strip()
                if clean_stmt:
                    await conn.execute(text(clean_stmt))
            logger.info("Olist e-commerce tables checked/created.")

        # 5. Seed data from CSV files (up to 500 rows to fit Neon limits)
        limit = 500
        
        # olist_customers
        logger.info("Seeding olist_customers...")
        cust_path = os.path.join(CSV_DIR, "olist_customers_dataset.csv")
        cust_inserted = 0
        if os.path.exists(cust_path):
            with open(cust_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                headers = next(reader)
                rows = []
                for r in reader:
                    if len(rows) >= limit: break
                    rows.append(r)
                insert_data = [
                    {"c1": row[0], "c2": row[1], "c3": int(row[2]) if row[2] else 0, "c4": row[3], "c5": row[4]}
                    for row in rows
                ]
                async with async_engine.begin() as conn:
                    await conn.execute(text("TRUNCATE TABLE olist_customers CASCADE;"))
                    await conn.execute(text("""
                        INSERT INTO olist_customers (customer_id, customer_unique_id, customer_zip_code_prefix, customer_city, customer_state)
                        VALUES (:c1, :c2, :c3, :c4, :c5) ON CONFLICT DO NOTHING;
                    """), insert_data)
                cust_inserted = len(insert_data)
            logger.info(f"Seeded {cust_inserted} customers.")
            
        # olist_products
        logger.info("Seeding olist_products...")
        prod_path = os.path.join(CSV_DIR, "olist_products_dataset.csv")
        prod_inserted = 0
        if os.path.exists(prod_path):
            with open(prod_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                headers = next(reader)
                rows = []
                for r in reader:
                    if len(rows) >= limit: break
                    rows.append(r)
                insert_data = [
                    {
                        "c1": row[0], "c2": row[1],
                        "c3": int(row[2]) if row[2] else None, "c4": int(row[3]) if row[3] else None,
                        "c5": int(row[4]) if row[4] else None, "c6": int(row[5]) if row[5] else None,
                        "c7": int(row[6]) if row[6] else None, "c8": int(row[7]) if row[7] else None,
                        "c9": int(row[8]) if row[8] else None
                    }
                    for row in rows
                ]
                async with async_engine.begin() as conn:
                    await conn.execute(text("TRUNCATE TABLE olist_products CASCADE;"))
                    await conn.execute(text("""
                        INSERT INTO olist_products (product_id, product_category_name, product_name_lenght, product_description_lenght, product_photos_qty, product_weight_g, product_length_cm, product_height_cm, product_width_cm)
                        VALUES (:c1, :c2, :c3, :c4, :c5, :c6, :c7, :c8, :c9) ON CONFLICT DO NOTHING;
                    """), insert_data)
                prod_inserted = len(insert_data)
            logger.info(f"Seeded {prod_inserted} products.")

        # olist_orders
        logger.info("Seeding olist_orders...")
        ord_path = os.path.join(CSV_DIR, "olist_orders_dataset.csv")
        ord_inserted = 0
        if os.path.exists(ord_path):
            with open(ord_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                headers = next(reader)
                rows = []
                res_c = await db.execute(text("SELECT customer_id FROM olist_customers;"))
                existing_custs = {row_c[0] for row_c in res_c.fetchall()}
                for r in reader:
                    if len(rows) >= limit: break
                    if r[1] in existing_custs:
                        rows.append(r)
                insert_data = [
                    {
                        "c1": row[0], "c2": row[1], "c3": row[2],
                        "c4": parse_date(row[3]), "c5": parse_date(row[4]),
                        "c6": parse_date(row[5]), "c7": parse_date(row[6]),
                        "c8": parse_date(row[7])
                    }
                    for row in rows
                ]
                async with async_engine.begin() as conn:
                    await conn.execute(text("TRUNCATE TABLE olist_orders CASCADE;"))
                    await conn.execute(text("""
                        INSERT INTO olist_orders (order_id, customer_id, order_status, order_purchase_timestamp, order_approved_at, order_delivered_carrier_date, order_delivered_customer_date, order_estimated_delivery_date)
                        VALUES (:c1, :c2, :c3, :c4, :c5, :c6, :c7, :c8) ON CONFLICT DO NOTHING;
                    """), insert_data)
                ord_inserted = len(insert_data)
            logger.info(f"Seeded {ord_inserted} orders.")

        # olist_order_items
        logger.info("Seeding olist_order_items...")
        items_path = os.path.join(CSV_DIR, "olist_order_items_dataset.csv")
        items_inserted = 0
        if os.path.exists(items_path):
            with open(items_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                headers = next(reader)
                rows = []
                res_p = await db.execute(text("SELECT product_id FROM olist_products;"))
                existing_prods = {row_p[0] for row_p in res_p.fetchall()}
                res_o = await db.execute(text("SELECT order_id FROM olist_orders;"))
                existing_orders = {row_o[0] for row_o in res_o.fetchall()}
                for r in reader:
                    if len(rows) >= limit: break
                    if r[0] in existing_orders and r[2] in existing_prods:
                        rows.append(r)
                insert_data = [
                    {
                        "c1": row[0], "c2": int(row[1]) if row[1] else 1, "c3": row[2], "c4": row[3],
                        "c5": parse_date(row[4]), "c6": float(row[5]) if row[5] else 0.0,
                        "c7": float(row[6]) if row[6] else 0.0
                    }
                    for row in rows
                ]
                async with async_engine.begin() as conn:
                    await conn.execute(text("TRUNCATE TABLE olist_order_items CASCADE;"))
                    await conn.execute(text("""
                        INSERT INTO olist_order_items (order_id, order_item_id, product_id, seller_id, shipping_limit_date, price, freight_value)
                        VALUES (:c1, :c2, :c3, :c4, :c5, :c6, :c7) ON CONFLICT DO NOTHING;
                    """), insert_data)
                items_inserted = len(insert_data)
            logger.info(f"Seeded {items_inserted} order items.")

        # olist_order_reviews
        logger.info("Seeding olist_order_reviews...")
        reviews_path = os.path.join(CSV_DIR, "olist_order_reviews_dataset.csv")
        reviews_inserted = 0
        if os.path.exists(reviews_path):
            with open(reviews_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                headers = next(reader)
                rows = []
                res_o = await db.execute(text("SELECT order_id FROM olist_orders;"))
                existing_orders = {row_o[0] for row_o in res_o.fetchall()}
                for r in reader:
                    if len(rows) >= limit: break
                    if r[1] in existing_orders:
                        rows.append(r)
                insert_data = [
                    {
                        "c1": row[0], "c2": row[1], "c3": int(row[2]) if row[2] else 5,
                        "c4": row[3], "c5": row[4], "c6": parse_date(row[5]),
                        "c7": parse_date(row[6])
                    }
                    for row in rows
                ]
                async with async_engine.begin() as conn:
                    await conn.execute(text("TRUNCATE TABLE olist_order_reviews CASCADE;"))
                    await conn.execute(text("""
                        INSERT INTO olist_order_reviews (review_id, order_id, review_score, review_comment_title, review_comment_message, review_creation_date, review_answer_timestamp)
                        VALUES (:c1, :c2, :c3, :c4, :c5, :c6, :c7) ON CONFLICT DO NOTHING;
                    """), insert_data)
                reviews_inserted = len(insert_data)
            logger.info(f"Seeded {reviews_inserted} order reviews.")

        # 6. Add "Olist E-commerce Store" as a DataSource in our App
        logger.info("Registering Olist datasource in metadata registries...")
        res_ds = await db.execute(select(DataSource).where(DataSource.name == "Olist E-commerce Store"))
        ds = res_ds.scalar_one_or_none()
        
        # Derive connection string parameters from settings.DATABASE_URL
        # We parse: postgresql://username:password@host:port/database
        db_conn_str = settings.DATABASE_URL
        # Strip sslmode details
        clean_conn = db_conn_str.split("?")[0]
        # Regex parse
        import re
        m = re.match(r"postgres(?:ql)?://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/(.+)", clean_conn)
        if m:
            username = m.group(1)
            password = m.group(2)
            host = m.group(3)
            port = int(m.group(4)) if m.group(4) else 5432
            database_name = m.group(5)
        else:
            username = None
            password = None
            host = "localhost"
            port = 5432
            database_name = "neondb"
            
        if not ds:
            ds = DataSource(
                user_id=user_id,
                name="Olist E-commerce Store",
                type="postgresql",
                description="Brazilian E-commerce public dataset containing tables for customers, products, orders, order items, and reviews."
            )
            
            db_conn = DatabaseConnection(
                host=host,
                port=port,
                username=username,
                password_encrypted=encrypt_credential(password) if password else None,
                database_name=database_name,
                schema_name="public"
            )
            ds.connection = db_conn
            db.add(ds)
            await db.flush()
            logger.info(f"Registered DataSource Olist E-commerce Store (ID: {ds.id})")
        else:
            logger.info(f"DataSource Olist E-commerce Store already registered (ID: {ds.id})")
            
        ds_id = ds.id
        
        # 7. Run Schema Discovery on the new DataSource
        logger.info("Discovering metadata fields...")
        # Clear old metadata if any
        res_meta = await db.execute(select(SchemaMetadata).where(SchemaMetadata.data_source_id == ds_id))
        old_meta = res_meta.scalars().all()
        for item in old_meta: await db.delete(item)
        
        res_rel = await db.execute(select(SchemaRelationship).where(SchemaRelationship.data_source_id == ds_id))
        old_rel = res_rel.scalars().all()
        for item in old_rel: await db.delete(item)
        await db.flush()
        
        # Perform discovery
        conn_dict = {
            "host": ds.connection.host,
            "port": ds.connection.port,
            "username": ds.connection.username,
            "password_encrypted": ds.connection.password_encrypted,
            "database_name": ds.connection.database_name,
            "schema_name": ds.connection.schema_name
        }
        
        discovery = SchemaDiscoveryService()
        cols, rels = await discovery.discover_schema(conn_dict, "postgresql")
        
        meta_objs = []
        for col in cols:
            meta_objs.append(SchemaMetadata(
                data_source_id=ds_id,
                table_name=col["table_name"],
                column_name=col["column_name"],
                data_type=col["data_type"],
                is_nullable=col["is_nullable"],
                is_primary_key=col["is_primary_key"],
                is_foreign_key=col["is_foreign_key"],
                description=col["description"]
            ))
        for m_obj in meta_objs: db.add(m_obj)
        
        rel_objs = []
        for rel in rels:
            rel_objs.append(SchemaRelationship(
                data_source_id=ds_id,
                source_table=rel["source_table"],
                source_column=rel["source_column"],
                target_table=rel["target_table"],
                target_column=rel["target_column"]
            ))
        for r_obj in rel_objs: db.add(r_obj)
        await db.flush()
        logger.info(f"Discovered {len(meta_objs)} columns and {len(rel_objs)} relationships.")
        
        # 8. Index metadata description embeddings via RAG
        logger.info("Computing RAG description embeddings...")
        rag = RAGService()
        await rag.index_schema(db, ds_id)
        
        await db.commit()
        logger.info("Database Seeding & Schema Indexing Completed Successfully!")
        
    await async_engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed_database())
