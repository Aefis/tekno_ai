"""
Simple Chainlit Chat App with Authentication and Historical Chat
---------------------------------------------------------------
Local-only demo — no external dependencies, database, or LLM.
User: admin / Password: admin
"""

import os
os.environ["CHAINLIT_AUTH_SECRET"] = "dev_secret_key_12345"

import chainlit as cl
from datetime import datetime

# In-memory history storage for demo
# Structure: { username: [ { "id": str, "timestamp": str, "messages": [] } ] }
chat_sessions = {}

# 1️⃣ Authentication
@cl.password_auth_callback
def auth_callback(username: str, password: str):
    """Simple single-user authentication."""
    if username == "admin" and password == "admin":
        return cl.User(identifier="admin", metadata={"role": "admin"})
    return None


# 2️⃣ When a new chat starts
@cl.on_chat_start
async def on_chat_start():
    """Show historical chat list when user logs in or starts new chat."""
    user = cl.user_session.get("user")
    username = user.identifier if user else "guest"

    # Initialize user's chat list
    if username not in chat_sessions:
        chat_sessions[username] = []

    # Display chat history summary
    history = chat_sessions[username]
    if history:
        msg = "🗂️ Here are your previous chats:\n\n"
        for i, chat in enumerate(history, 1):
            msg += f"{i}. {chat['timestamp']}  (id: {chat['id']})\n"
        msg += "\nType the chat number to reopen it, or start a new conversation below."
    else:
        msg = "👋 Welcome! You don't have any saved chats yet."

    await cl.Message(content=msg).send()

    # Initialize new empty chat history for this session
    cl.user_session.set("current_chat", {"id": str(len(history) + 1),
                                         "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                         "messages": []})


# 3️⃣ Handle incoming user messages
@cl.on_message
async def on_message(message: cl.Message):
    """Handles user messages and stores chat locally."""
    user = cl.user_session.get("user")
    username = user.identifier if user else "guest"
    chat = cl.user_session.get("current_chat")

    # Check if user wants to open an older chat
    if message.content.strip().isdigit():
        idx = int(message.content.strip()) - 1
        if 0 <= idx < len(chat_sessions[username]):
            old_chat = chat_sessions[username][idx]
            await cl.Message(content=f"📜 Reopening chat from {old_chat['timestamp']}...").send()
            for msg in old_chat["messages"]:
                await cl.Message(author=msg["role"], content=msg["content"]).send()
            return
        else:
            await cl.Message(content="❌ Invalid chat number.").send()
            return

    # Otherwise, normal message flow
    chat["messages"].append({"role": "user", "content": message.content})

    # Simple echo-style bot response (no LLM)
    reply = f"🤖 You said: {message.content}"
    chat["messages"].append({"role": "assistant", "content": reply})

    await cl.Message(content=reply).send()


# 4️⃣ When the chat ends — store it in memory
@cl.on_chat_end
async def on_chat_end():
    """Save chat to history when user leaves or restarts."""
    user = cl.user_session.get("user")
    username = user.identifier if user else "guest"
    chat = cl.user_session.get("current_chat")

    if chat and chat["messages"]:
        chat_sessions[username].append(chat)
        print(f"✅ Saved chat {chat['id']} for {username}")


# ✅ Run this app with:
# chainlit run app.py -w
