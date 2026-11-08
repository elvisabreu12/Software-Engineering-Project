import os
import sys
from contextlib import asynccontextmanager
from typing import List, Literal

import anthropic
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
# from database import SessionLocal, get_db   
# from models import InternalComment
load_dotenv()

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from database import SessionLocal, get_db
from models import InternalComment

chroma_client = chromadb.PersistentClient(path=os.path.join(HERE, "chroma_data"))

embedding_function = embedding_functions.DefaultEmbeddingFunction()

collection = chroma_client.get_or_create_collection(
    name="internal_comments",
    embedding_function=embedding_function,
    metadata={"hnsw:space": "cosine"}, 
)

anthropic_client = anthropic.Anthropic()

THRESHOLD_DISTANCE = 0.7

SYSTEM_PROMPT = """You are an IT helpdesk assistant.
Your ONLY source of information is the <knowledge_base> in the user's message. It containsnotes notes from our IT team when they resolved past tickets.

Rules:
- Answer using only what the notes say. Do NOT use outside knowledge, guesses, or general IT advice.
- If the notes do not contain enough to answer the question, say so plainly and suggest the
  user open a new ticket. Do not try to fill the gap yourself.
- Be concise and give steps when the notes contain steps."""

def sync_internal_comments(db: Session) -> int:
    """Rebuilds the knowledge base from InternalComments. Only the note text is stored:
       no ticket titles, ticket descriptions or customer-visible comments."""
       
    existing = collection.get()["ids"]
    if existing:
        collection.delete(ids=existing)

    ids, documents, metadatas = [], [], []
    for comment in db.query(InternalComment).all():
        text = (comment.internal_comment_desc or "").strip()
        if text:
            ids.append(str(comment.internal_comment_id))
            documents.append(text)
            metadatas.append({
                "ticket_id": comment.ticket_id,
                "internal_comment_id": comment.internal_comment_id
            })
    if ids:
        collection.add(ids=ids, documents=documents, metadatas=metadatas)
    return len(ids)

def search_knowledge_base(query: str, n_results: int = 3):
    """Retuns [(ticket_id, note_text), ...] for the notes closests in meaning to the query."""
    if collection.count() == 0:
        return []
    results = collection.query(query_texts=[query], n_results=n_results)
    hits = []
    for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
        if dist <= THRESHOLD_DISTANCE:
            hits.append((meta["ticket_id"], doc))
    return hits

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Build the knowledge base when the server starts
    try:
        db = SessionLocal()
        try:
            count = sync_internal_comments(db)
        finally:
            db.close()
        print(f"Knowledge base ready: {count} internal comments indexed")
    except Exception as e:
        print("Startup sync failed (use POST /sync-knowledge-base to retry):", e)
    yield

app = FastAPI(title="Helpdesk Chatbot", lifespan=lifespan)
    
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://whiterabbit.com", "http://localhost:3000",
                   "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.post("/sync-knowledge-base")
def sync_knowledge_base(db: Session = Depends(get_db)):
    """Rebuilds the knowledge base from InternalComments."""
    count = sync_internal_comments(db)
    return {"message": f"Synced {count} internal comments indexed."}

@app.get("/search-knowledge-base")
def search_kb(query: str, n_results: int = 5):
    hits = search_knowledge_base(query, n_results)
    return [{"ticket_id": ticket_id, "note_text": note_text} for ticket_id, note_text in hits]

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatRequest(BaseModel):
    question: str = Field(..., max_length=700)
    history: List[ChatMessage] = []

@app.post("/chat")
def chat(request: ChatRequest):
    """Answer a user's question using ONLY internal comments."""
    history_t = list(request.history[-10:])
    while history_t and history_t[0].role != "user":
        history_t.pop(0)

    prev_user_messages = [m.content for m in history_t if m.role == "user"]
    search_text = " ".join(prev_user_messages[-1:] + [request.question])

    hits = search_knowledge_base(search_text, n_results=3)

    if hits:
        context = "\n\n".join(f"Ticket: #{ticket_id}\n{note_text}" for ticket_id, note_text in hits)
    else:
        context = "no results found" 

    messages = [{"role": m.role, "content": m.content} for m in history_t]
    messages.append({
        "role": "user",
        "content": f"<knowledge_base>\n{context}\n</knowledge_base>\n\nQuestion: {request.question}",
    })

    try:
        response = anthropic_client.messages.create(
            model = "claude-sonnet-5-5",
            max_tokens = 1000,
            system = SYSTEM_PROMPT,
            messages = messages,
        )
    except anthropic.APIError:
        raise HTTPException(status_code=500, detail="Error cant connect to the AI service.")
    answer = "".join(block.text for block in response.content if block.type == "text")

    return {
    "answer": answer,
    "sources": sorted({t for t, _ in hits}),
    }
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "chatbot_widget")), name = "static")

