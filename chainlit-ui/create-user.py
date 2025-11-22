import os
import psycopg2
import json
import bcrypt
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cursor = conn.cursor()

# --- Input user data ---
username = input("Username: ").strip()
password = input("Password: ").strip()

# --- Hash password ---
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

# --- Insert into database ---
cursor.execute(
    '''
    INSERT INTO "User" ("identifier", "password", "metadata")
    VALUES (%s, %s, %s)
    ''',
    (username, hashed, json.dumps({}))   # Empty metadata {}
)

conn.commit()
conn.close()

print("✅ User created successfully!")