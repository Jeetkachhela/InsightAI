# Database Backup and Disaster Recovery Plan - InsightForge AI

This document details the strategies and operational scripts for backup, replication, and disaster recovery of the InsightForge AI platform databases.

---

## 💾 1. PostgreSQL (Neon Production Backup)

Neon PostgreSQL databases support instant Point-in-Time Recovery (PITR) and automated daily snapshots. In addition to cloud provider snapshots, we maintain logical database backups.

### Automated Logical Backups (pg_dump)
We run daily automated cron jobs utilizing `pg_dump` to create compressed SQL dumps.

**Backup Command:**
```bash
pg_dump "postgresql://neondb_owner:npg_nO1HpZzXWD9o@ep-solitary-resonance-atm3rnj0-pooler.c-9.us-east-1.aws.neon.tech/neondb?sslmode=require" -F c -b -v -f insightforge_prod_backup_$(date +%F).dump
```

**Restoration/Recovery Procedure:**
To restore a snapshot in case of failure or data corruption:
1. Re-initialize a blank database schema.
2. Run the `pg_restore` command targeting the selected dump file:
   ```bash
   pg_restore -d "postgresql://neondb_owner:npg_nO1HpZzXWD9o@ep-solitary-resonance-atm3rnj0-pooler.c-9.us-east-1.aws.neon.tech/neondb?sslmode=require" -v -c -O insightforge_prod_backup_YYYY-MM-DD.dump
   ```
3. Re-run embedding indexing to synchronize vector data (if needed, see section 3).

---

## 🗄️ 2. SQLite (Development & Local Backup)

For local development or single-tenant SQLite deployments, we use database file copy strategies.

**Backup Script (Windows PowerShell):**
```powershell
# Copy sqlite database safely
Copy-Item "backend/insightforge.db" "backend/backups/insightforge_backup_$(Get-Date -Format 'yyyy-MM-dd').db" -Force
```

**Restoration Procedure:**
1. Stop the backend dev server process.
2. Rename/replace the corrupted DB:
   ```powershell
   Rename-Item "backend/insightforge.db" "backend/insightforge_corrupt.db"
   Copy-Item "backend/backups/insightforge_backup_YYYY-MM-DD.db" "backend/insightforge.db" -Force
   ```
3. Start the backend service.

---

## 🧠 3. RAG Embeddings Vector Store Reconstruction

If the database is restored from a backup that lags behind or lacks pgvector entries, you can re-index all data sources to rebuild embeddings.

**Command to Re-Index All Schemas:**
To force the system to reconstruct description embeddings and sync vector tables, run the seeding script:
```bash
python backend/seed_db.py
```
This script runs the `SchemaDiscoveryService` and `RAGService` to regenerates embeddings for all active tables and columns.
