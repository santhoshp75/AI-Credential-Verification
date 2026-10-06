import sqlite3

DB_NAME = "database.db"

conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

# Add validation_code column if it does not already exist
try:
    cursor.execute("""
        ALTER TABLE certificate_uploads
        ADD COLUMN validation_code TEXT
    """)
    print("✅ validation_code column added")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e).lower():
        print("✅ validation_code column already exists")
    else:
        print("❌ Error:", e)

# Add other useful columns if missing
columns = [
    ("student_name", "TEXT"),
    ("organization", "TEXT"),
    ("credential_id", "TEXT"),
    ("certificate_type", "TEXT"),
    ("status", "TEXT"),
    ("uploaded_at", "TEXT")
]

for column_name, column_type in columns:
    try:
        cursor.execute(
            f"ALTER TABLE certificate_uploads ADD COLUMN {column_name} {column_type}"
        )
        print(f"✅ Added column: {column_name}")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print(f"✔ Already exists: {column_name}")
        else:
            print(f"⚠️ {column_name}: {e}")

conn.commit()
conn.close()

print("\n✅ Database update completed successfully.")