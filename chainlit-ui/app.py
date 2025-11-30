"""
Simple Chainlit Chat App with Authentication and Historical Chat
---------------------------------------------------------------
"""
import os
import bcrypt
import psycopg2
import chainlit as cl
from dotenv import load_dotenv

# -----------------------------------------
#      LlamaIndex + Qdrant INITIALIZATION
# -----------------------------------------
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from qdrant_client import QdrantClient, AsyncQdrantClient
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.openai import OpenAI

load_dotenv()

# Load env values
qdrant_url = os.getenv("QDRANT_URL")
qdrant_api_key = os.getenv("QDRANT_API_KEY")
model_name = "BAAI/bge-m3"
# Qdrant clients
client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
aclient = AsyncQdrantClient(url=qdrant_url, api_key=qdrant_api_key)

# Vector store
vector_store = QdrantVectorStore(
    client=client,
    aclient=aclient,
    collection_name="legal_BAAI_bge-m3"
)

# Embeddings
embed_model = HuggingFaceEmbedding(
    # model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_name=model_name,
    device="cpu",
)

# Storage + Index
storage_context = StorageContext.from_defaults(vector_store=vector_store)

index = VectorStoreIndex.from_vector_store(
    vector_store=vector_store,
    storage_context=storage_context,
    embed_model=embed_model,
)

# Query engine
query_engine = index.as_query_engine()


# ============= TOOL =============
async def search_documents(query: str):
    response = await query_engine.aquery(query)
    return {
        "answer": str(response),
        "sources": [node.text[:200] for node in response.source_nodes]
    }

# ============= AGENT =============
system_prompt = """
You are an AI assistant whose primary source of truth is the information retrieved by the search_documents tool.

When you receive a tool result, you MUST:
1. Carefully read the full text and metadata returned by the tool.
2. Synthesize a rich, detailed, and well-structured answer.
3. Use the metadata whenever relevant.
4. Integrate multiple retrieved chunks into one coherent explanation.
5. Provide context, significance, relationships.
6. Never invent facts not found in the documents.
7. If information is missing, state what is missing.
8. Give detailed, rich, structured responses.
9. Use only the tool’s output as your knowledge base.
"""

agent = FunctionAgent(
    tools=[search_documents],
    llm=OpenAI(model="gpt-4o-mini"),
    require_tools=True,
    system_prompt=system_prompt,
)

# --- PostgreSQL connection ---
# conn = psycopg2.connect(os.getenv("DATABASE_URL"))
# cursor = conn.cursor()

# # Chainlit auth callback
# @cl.password_auth_callback
# def auth_callback(username, password):
#     # Fetch user from database
#     cursor.execute(
#     'SELECT "identifier", "password", "metadata" FROM "User" WHERE "identifier" = %s',
#     (username,)
#     )
#     row = cursor.fetchone()

#     if not row:
#         return None

#     identifier, password_hash, metadata = row

#     # Check bcrypt password
#     if bcrypt.checkpw(password.encode(), password_hash.encode()):
#         return cl.User(
#             identifier=identifier,
#             metadata=metadata if metadata else {}
#         )

#     return None



# 2️⃣ When a new chat starts
@cl.on_chat_start
async def on_chat_start():
    """Show historical chat list when user logs in or starts new chat."""
    msg = "This is a trak-ai chatbot you can only ask it for a law questions"
    await cl.Message(content=msg).send()


# 3️⃣ Handle incoming user messages
@cl.on_message
async def on_message(message: cl.Message):

    user_query = message.content

    # Temporary loading message
    msg = cl.Message(content="⏳ Processing your request…")
    await msg.send()

    try:
        # Run your agent
        result = await agent.run(user_query)

        # Convert AgentOutput → text
        if hasattr(result, "response") and hasattr(result.response, "message"):  
            # LlamaIndex AgentOutput object
            content = result.response.message.content
        else:
            # Fallback: just stringify
            content = str(result)

    except Exception as e:
        content = f"❌ Error: {str(e)}"

    # Update the Chainlit message safely
    msg.content = content
    await msg.update()





# ✅ Run this app with:
# chainlit run app.py -w
