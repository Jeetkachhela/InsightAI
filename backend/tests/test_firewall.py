import pytest
from app.core.security import is_safe_select_query

def test_safe_select():
    # Simple selects
    safe, msg = is_safe_select_query("SELECT * FROM users;")
    assert safe is True, msg
    
    # Joins and group bys
    safe, msg = is_safe_select_query("""
        SELECT u.email, COUNT(o.id) as order_count 
        FROM users u 
        LEFT JOIN orders o ON u.id = o.user_id 
        WHERE o.status = 'completed'
        GROUP BY u.email 
        HAVING COUNT(o.id) > 5;
    """)
    assert safe is True, msg

def test_blocked_ddl():
    # DROP
    safe, msg = is_safe_select_query("DROP TABLE users;")
    assert safe is False
    assert "blocked" in msg.lower() or "keyword" in msg.lower()
    
    # ALTER
    safe, msg = is_safe_select_query("ALTER TABLE users ADD COLUMN age INT;")
    assert safe is False
    
    # CREATE
    safe, msg = is_safe_select_query("CREATE TABLE test (id INT);")
    assert safe is False

def test_blocked_dml_writes():
    # INSERT
    safe, msg = is_safe_select_query("INSERT INTO users (email, password_hash) VALUES ('test@test.com', 'hash');")
    assert safe is False
    
    # UPDATE
    safe, msg = is_safe_select_query("UPDATE users SET email = 'hacker@test.com' WHERE id = 1;")
    assert safe is False
    
    # DELETE
    safe, msg = is_safe_select_query("DELETE FROM users WHERE id = 1;")
    assert safe is False

def test_blocked_multi_statement():
    # Multi-statement injection
    safe, msg = is_safe_select_query("SELECT * FROM users; DROP TABLE orders;")
    assert safe is False
    assert "multi-statement" in msg.lower()

def test_blocked_nested_writes():
    # Subquery writes or side-channel writes
    safe, msg = is_safe_select_query("SELECT * FROM (DELETE FROM users);")
    assert safe is False
    
    safe, msg = is_safe_select_query("SELECT name INTO backup_table FROM users;")
    assert safe is False
    
    safe, msg = is_safe_select_query("SELECT * FROM users WHERE id = (UPDATE orders SET status = 'hack' RETURNING id);")
    assert safe is False

def test_obfuscation_attempts():
    # Capitalization tricks
    safe, msg = is_safe_select_query("DeLeTe FROM users;")
    assert safe is False
    
    # Comments embedding forbidden words
    # While valid sql comments might have names, a strict firewall blocks them if keywords occur in commands
    safe, msg = is_safe_select_query("SELECT * FROM users; -- drop table orders")
    assert safe is False  # Multi-statement blocking catches this, or keyword check
