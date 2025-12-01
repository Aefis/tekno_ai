import os
import chainlit as cl
from dotenv import load_dotenv

from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from qdrant_client import QdrantClient, AsyncQdrantClient

from llama_index.core.prompts import PromptTemplate

load_dotenv()

# ============================================================
# QDRANT
# ============================================================

qdrant_url = os.getenv("QDRANT_URL")
qdrant_api_key = os.getenv("QDRANT_API_KEY")

client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
aclient = AsyncQdrantClient(url=qdrant_url, api_key=qdrant_api_key)

# ============================================================
# EMBEDDINGS
# ============================================================
model_name = "sentence-transformers/all-MiniLM-L6-v2"
model_name = "BAAI/bge-m3"
embed_model = HuggingFaceEmbedding(
    model_name=model_name,
    device="cpu"
)

# ============================================================
# VECTOR STORE + INDEX
# ============================================================

vector_store = QdrantVectorStore(
    client=client,
    aclient=aclient,
    collection_name="legal_BAAI_bge-m3"
)

storage_context = StorageContext.from_defaults(vector_store=vector_store)

index = VectorStoreIndex.from_vector_store(
    vector_store=vector_store,
    storage_context=storage_context,
    embed_model=embed_model
)

# ============================================================
# PROMPT JURIDIQUE
# ============================================================

qa_tmpl = PromptTemplate("""
Vous êtes un moteur juridique. Répondez STRICTEMENT d'après les extraits fournis.

Chaque extrait inclut :
- son texte
- ses métadonnées (titre, type d'acte, numéro, date, chapitre)

Utilisez activement ces métadonnées pour éviter toute confusion entre directives.

=== CONTEXTE ===
{context_str}

=== METADONNEES ===
{metadata_str}
Parle moi d'une loi importante dans le cadre de l'environnement en Europe.
=== QUESTION ===
{query_str}

Réponse détaillée et fidèle au texte et dans la même langue que l'utilisateur:
""")

# ============================================================
# QUERY ENGINE
# ============================================================

query_engine = index.as_query_engine(
    similarity_top_k=30,
    rerank_top_k=10,
    verbose=True,
    response_mode="tree_summarize",
    text_qa_template=qa_tmpl
)

# ============================================================
# CHAINLIT CALLBACKS
# ============================================================

@cl.on_chat_start
async def start():
    await cl.Message("This is a trak-ai legal chatbot. Ask legal questions only.").send()


@cl.on_message
async def main(message: cl.Message):

    loading = cl.Message("⏳ Processing your request…")
    await loading.send()

    try:
        # Appel direct au query engine juridique
        response = await query_engine.aquery(message.content)
        content = response.response

    except Exception as e:
        content = f"❌ Error: {str(e)}"

    loading.content = content
    await loading.update()
