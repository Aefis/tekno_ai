import os
import chainlit as cl
from chainlit.input_widget import Switch, Slider
from chainlit.types import ThreadDict
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
# PROMPT JURIDIQUE (avec historique)
# ============================================================

qa_tmpl_with_history = PromptTemplate("""
Vous êtes un assistant juridique intelligent. Vous êtes en conversation continue avec l'utilisateur.

IMPORTANT: Tenez compte de l'HISTORIQUE DE CONVERSATION ci-dessous pour comprendre le contexte.
Si l'utilisateur fait référence à "ça", "cela", "ce sujet", etc., référez-vous à l'historique.

Chaque extrait de document inclut :
- son texte
- ses métadonnées (titre, type d'acte, numéro, date, chapitre)

=== CONTEXTE DOCUMENTAIRE ===
{context_str}

=== METADONNEES ===
{metadata_str}

=== QUESTION ACTUELLE (avec historique) ===
{query_str}

Répondez de manière détaillée et cohérente avec la conversation en cours, dans la même langue que l'utilisateur:
""")

qa_tmpl_no_history = PromptTemplate("""
Vous êtes un moteur juridique. Répondez STRICTEMENT d'après les extraits fournis.

Chaque extrait inclut :
- son texte
- ses métadonnées (titre, type d'acte, numéro, date, chapitre)

Utilisez activement ces métadonnées pour éviter toute confusion entre directives.

=== CONTEXTE ===
{context_str}

=== METADONNEES ===
{metadata_str}

=== QUESTION ===
{query_str}

Réponse détaillée et fidèle au texte et dans la même langue que l'utilisateur:
""")

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def format_chat_history(history: list, max_messages: int = 10) -> str:
    """Formate l'historique de chat pour l'inclure dans le prompt."""
    if not history:
        return ""
    
    # Limiter aux derniers échanges (paires question/réponse)
    recent_history = history[-max_messages:]
    
    formatted = ["HISTORIQUE DE LA CONVERSATION:"]
    for i, msg in enumerate(recent_history):
        role = "👤 Utilisateur" if msg["role"] == "user" else "🤖 Assistant"
        # Tronquer les messages trop longs
        content = msg['content'][:500] + "..." if len(msg['content']) > 500 else msg['content']
        formatted.append(f"{role}: {content}")
    formatted.append("---")
    
    return "\n".join(formatted)

# ============================================================
# CHAINLIT CALLBACKS
# ============================================================

@cl.on_chat_start
async def start():
    # Initialiser l'historique de conversation (stocké en session)
    cl.user_session.set("chat_history", [])
    cl.user_session.set("history_enabled", True)
    cl.user_session.set("max_history_messages", 10)
    
    # Configurer les settings (accessibles via l'icône ⚙️)
    settings = await cl.ChatSettings(
        [
            Switch(
                id="history_enabled",
                label="Activer l'historique de conversation",
                initial=True
            ),
            Slider(
                id="max_history_messages",
                label="Nombre max de messages dans l'historique",
                initial=10,
                min=2,
                max=30,
                step=2
            )
        ]
    ).send()
    
    await cl.Message("🏛️ Bienvenue sur le chatbot juridique Trak-AI. Posez vos questions juridiques !").send()


@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    """Restaure une conversation depuis l'historique (sidebar)."""
    # Reconstruire l'historique à partir des steps
    chat_history = []
    
    for step in thread.get("steps", []):
        if step.get("type") == "user_message":
            chat_history.append({"role": "user", "content": step.get("output", "")})
        elif step.get("type") == "assistant_message":
            chat_history.append({"role": "assistant", "content": step.get("output", "")})
    
    # Restaurer l'historique dans la session
    cl.user_session.set("chat_history", chat_history)
    cl.user_session.set("history_enabled", True)
    cl.user_session.set("max_history_messages", 10)


@cl.on_settings_update
async def settings_update(settings):
    """Callback quand les settings sont modifiés."""
    cl.user_session.set("history_enabled", settings["history_enabled"])
    cl.user_session.set("max_history_messages", int(settings["max_history_messages"]))
    
    status = "activé" if settings["history_enabled"] else "désactivé"
    await cl.Message(f"⚙️ Historique {status} (max: {int(settings['max_history_messages'])} messages)").send()


@cl.on_message
async def main(message: cl.Message):
    loading = cl.Message("⏳ Traitement de votre demande…")
    await loading.send()

    try:
        # Récupérer les settings
        history_enabled = cl.user_session.get("history_enabled", True)
        max_messages = cl.user_session.get("max_history_messages", 10)
        chat_history = cl.user_session.get("chat_history", [])
        
        # Construire la requête avec ou sans historique
        if history_enabled and chat_history:
            history_str = format_chat_history(chat_history, max_messages)
            
            query_engine_with_history = index.as_query_engine(
                similarity_top_k=30,
                rerank_top_k=10,
                verbose=True,
                response_mode="tree_summarize",
                text_qa_template=qa_tmpl_with_history
            )
            
            augmented_query = f"{history_str}\n\n👤 NOUVELLE QUESTION: {message.content}"
            response = await query_engine_with_history.aquery(augmented_query)
        else:
            query_engine_no_history = index.as_query_engine(
                similarity_top_k=30,
                rerank_top_k=10,
                verbose=True,
                response_mode="tree_summarize",
                text_qa_template=qa_tmpl_no_history
            )
            response = await query_engine_no_history.aquery(message.content)
        
        content = response.response
        
        # Sauvegarder dans l'historique si activé
        if history_enabled:
            chat_history.append({"role": "user", "content": message.content})
            chat_history.append({"role": "assistant", "content": content})
            cl.user_session.set("chat_history", chat_history)

    except Exception as e:
        content = f"❌ Erreur: {str(e)}"

    # Supprimer le message de chargement
    await loading.remove()
    
    # Créer les boutons de feedback 👍👎
    actions = [
        cl.Action(
            name="thumbs_up",
            payload={"value": "positive"},
            label="👍",
            description="Bonne réponse"
        ),
        cl.Action(
            name="thumbs_down",
            payload={"value": "negative"},
            label="👎",
            description="Mauvaise réponse"
        )
    ]
    
    # Envoyer la réponse avec les boutons de feedback
    await cl.Message(content=content, actions=actions).send()


@cl.action_callback("thumbs_up")
async def on_thumbs_up(action: cl.Action):
    """Feedback positif."""
    await cl.Message(content="✅ Merci pour votre feedback positif !").send()


@cl.action_callback("thumbs_down")
async def on_thumbs_down(action: cl.Action):
    """Feedback négatif."""
    await cl.Message(content="📝 Merci pour votre feedback. Nous allons nous améliorer !").send()
