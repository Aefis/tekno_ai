"""
Chainlit + LlamaIndex + Qdrant
-----------------------------------------
Recommandé : FunctionAgent (stable tool-calling)
"""

import os
import chainlit as cl
from dotenv import load_dotenv

from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from qdrant_client import QdrantClient, AsyncQdrantClient
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.openai import OpenAI
from llama_index.core.memory import ChatMemoryBuffer


load_dotenv()

# Qdrant
qdrant_url = os.getenv("QDRANT_URL")
qdrant_api_key = os.getenv("QDRANT_API_KEY")

client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
aclient = AsyncQdrantClient(url=qdrant_url, api_key=qdrant_api_key)

# Memory
memory = ChatMemoryBuffer.from_defaults(token_limit=5000)

# Embedding model
embed_model = HuggingFaceEmbedding(
    model_name="BAAI/bge-m3",
    device="cpu"
)

# Vector store
vector_store = QdrantVectorStore(
    client=client,
    aclient=aclient,
    collection_name="legal_BAAI_bge-m3"
)

# Storage + index
storage_context = StorageContext.from_defaults(vector_store=vector_store)
index = VectorStoreIndex.from_vector_store(
    vector_store=vector_store,
    storage_context=storage_context,
    embed_model=embed_model,
)

query_engine = index.as_query_engine()


# ============================================================
# TOOL
# ============================================================

async def search_documents(query: str):
    response = await query_engine.aquery(
        query,
        similarity_top_k=30,
    )

    sources = []
    for node in response.source_nodes:
        sources.append({
            "id": node.node_id,
            "text": node.text,
            "metadata": dict(node.metadata) if node.metadata else {},
            "score": float(node.score)
        })
    return {
        "answer": response.response,
        "sources": sources
    }


# ============================================================
# AGENT FunctionAgent (RECOMMANDÉ)
# ============================================================

system_prompt ="""
Vous êtes un moteur juridique. Répondez STRICTEMENT d'après les extraits fournis.

Chaque extrait inclut :
- son texte
- ses métadonnées (titre, type d'acte, numéro, date, chapitre)

Utilisez activement ces métadonnées pour éviter toute confusion entre directives.

Réponse détaillée et fidèle au texte et dans la même langue que l'utilisateur:
"""

agent = FunctionAgent(
    tools=[search_documents],
    llm=OpenAI(model="gpt-4o-mini"),
    system_prompt=system_prompt,
    memory=memory,
)


# ============================================================
# CHAINLIT CALLBACKS
# ============================================================

@cl.on_chat_start
async def start():
    await cl.Message("This is a track-ai legal chatbot. Ask legal questions only.").send()


@cl.on_message
async def main(message: cl.Message):

    loading = cl.Message("⏳ Processing your request…")
    await loading.send()

    try:
        result = await agent.run(message.content)
        content = result.response.content


    except Exception as e:
        content = f"❌ Error: {str(e)}"

    loading.content = content
    await loading.update()
