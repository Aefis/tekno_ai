"""
Simple Chainlit Chat App with Authentication and Historical Chat
---------------------------------------------------------------
"""
import os
import bcrypt
import psycopg2
import chainlit as cl
from dotenv import load_dotenv

load_dotenv()

# --- PostgreSQL connection ---
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cursor = conn.cursor()

# Chainlit auth callback
@cl.password_auth_callback
def auth_callback(username, password):
    # Fetch user from database
    cursor.execute(
    'SELECT "identifier", "password", "metadata" FROM "User" WHERE "identifier" = %s',
    (username,)
    )
    row = cursor.fetchone()

    if not row:
        return None

    identifier, password_hash, metadata = row

    # Check bcrypt password
    if bcrypt.checkpw(password.encode(), password_hash.encode()):
        return cl.User(
            identifier=identifier,
            metadata=metadata if metadata else {}
        )

    return None



# 2️⃣ When a new chat starts
@cl.on_chat_start
async def on_chat_start():
    """Show historical chat list when user logs in or starts new chat."""
    msg = "This is a trak-ai chatbot you can only ask it for a law questions"
    await cl.Message(content=msg).send()


# 3️⃣ Handle incoming user messages
@cl.on_message
async def on_message(message: cl.Message):
    """Handles user messages and stores chat locally."""
    # Simple echo-style bot response (no LLM)
    reply = f"🤖 You said: {message.content}"

    await cl.Message(content=reply).send()


# ✅ Run this app with:
# chainlit run app.py -w
