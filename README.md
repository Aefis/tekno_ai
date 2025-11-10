# 💬 Simple Chainlit Chat App (Local Authentication + Chat History)

This is a minimal **Chainlit** chat application featuring:
- 🔐 Basic login (single user: `admin` / `admin`)
- 💾 In-memory chat history (each chat saved while the app runs)
- 🧭 Option to reopen older conversations
- ⚙️ 100% local — **no Ollama, no database, no external API**

---

## 🧩 Features
- Simple password-based authentication via `@cl.password_auth_callback`
- Automatic storage of chat history in memory
- Historical chat selection (type a number to reopen)
- Works out-of-the-box for local testing

---

## 🛠️ Requirements

### 1. Python
Make sure you have **Python 3.9+**

### 2. Install Dependencies
Create a virtual environment (recommended) and install required packages:

```bash
pip install chainlit matplotlib python-dotenv
```


```bash
chainlit run .\app.py
```
