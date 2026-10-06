import sqlite3

DB_NAME = "database.db"

conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

# =====================================================
# USERS TABLE
# =====================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT UNIQUE,
    password TEXT,
    credential_id TEXT,
    certificate_type TEXT,
    university TEXT,
    course TEXT,
    year TEXT,
    validation_code TEXT,
    certificate_file TEXT,
    created_at TEXT
)
""")

# =====================================================
# CERTIFICATE UPLOADS TABLE
# =====================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS certificate_uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    credential_id TEXT,
    filename TEXT,
    file_path TEXT,
    uploaded_at TEXT
)
""")

# =====================================================
# VERIFICATION HISTORY TABLE
# =====================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS verification_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    credential_id TEXT,
    certificate_type TEXT,
    status TEXT,
    detected_name TEXT,
    detected_university TEXT,
    verified_at TEXT
)
""")

# =====================================================
# ADMINS TABLE
# =====================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT
)
""")

conn.commit()

print()
print("========================================")
print(" DATABASE FIX COMPLETED")
print("========================================")
print("users                  : OK")
print("certificate_uploads    : OK")
print("verification_history   : OK")
print("admins                 : OK")
print("========================================")

conn.close()