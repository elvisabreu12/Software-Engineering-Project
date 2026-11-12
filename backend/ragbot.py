import os
import sys
from contextlib import asynccontextmanager
from typing import List, Literal

import anthropic
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
# from sqlalchemy import text
from sqlalchemy.orm import Session

load_dotenv()  # loads ANTHROPIC_API_KEY, DATABASE_URL, RAGBOT_SYNC_KEY from .env

# gets current folder 
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)) #allows us to import modules from the parent project directory.

from database import SessionLocal, get_db
from models import InternalComment, Ticket 

# PersistentClient saves the vectors to the "chroma_data" folder, so the knowledge base survives a server restart.
chroma_client = chromadb.PersistentClient(path=os.path.join(HERE, "chroma_data"))

# The default embedding model runs locally on this computer
embedding_function = embedding_functions.DefaultEmbeddingFunction()

#creates collection
collection = chroma_client.get_or_create_collection(
    name="internal_comments",
    embedding_function=embedding_function,  #Tells ChromaDB which embedding function to use when storing and searching text
    metadata={"hnsw:space": "cosine"}, #measured by the similarity of the vectors, not their distance. 0 = identical, 1 = very different
)

anthropic_client = anthropic.Anthropic()#reads key from env

THRESHOLD_DISTANCE = 0.7
SYNC_KEY = os.getenv("RAGBOT_SYNC_KEY") # reads sync key from env

# The instructions that tell Claude how to behave. NO EXTERNAL DATA!
SYSTEM_PROMPT = """You are an IT helpdesk assistant.
Your ONLY source of information is the <knowledge_base> in the user's message. Each entry is a past ticket with:
  - IT note: what our IT team wrote when they worked on or resolved it
 
Rules:
- Answer using only what the entries say. Do NOT use outside knowledge, guesses, or general IT advice.
- Match the user's problem to the entry's Problem and Ticket title, then give the fix from the IT note.
- If the IT note only hints at a cause (for example "likely a battery issue") say it is a likely cause, not a confirmed fix.
- Never mention a ticket's priority or urgency level.
- If the entries do not contain enough to answer, say so plainly and suggest the user open a new ticket. Do not fill the gap yourself.
- Be concise. Use short numbered steps when the note contains steps.
"""


def build_document(comment: InternalComment, ticket: Ticket | None) -> str:  
    """The text that gets embedded: the ticket's title and description plus the IT note.
       This is what lets the bot match a question like 'my laptop won't turn on'
       to the right note even when the note itself is short."""
    note = (comment.internal_comment_desc or "").strip()  
    if not note:
        return ""
    if ticket is None:
        return f"IT note: {note}"
    lines = [f"Ticket #{ticket.ticket_id}: {(ticket.title or '').strip()}"] #creates a list that containts ticket information
    if ticket.ticket_desc and ticket.ticket_desc.strip():
        lines.append(f"Problem: {ticket.ticket_desc.strip()}") #if ticket has description it add the description to the list
    if ticket.category:
        lines.append(f"Category: {ticket.category.category_name}")#if ticket has category it add the category to the list
    lines.append(f"IT note: {note}") # adds the IT note to the list
    return "\n".join(lines)

def sync_internal_comments(db: Session) -> int:
    """Rebuilds the knowledge base from InternalComments. Only the note text is stored:
       no ticket titles, ticket descriptions or customer-visible comments."""
       
    current = {} #creates disctionary for current internal comments
    for comment in db.query(InternalComment).all(): #gets internal comments from the database
        ticket = db.query(Ticket).filter(Ticket.ticket_id == comment.ticket_id).first()
        text = build_document(comment, ticket)
        #Uses the internal comment ID as the dictionary key. Stores the document text and its associated ticket ID.
        if text:
            current[str(comment.internal_comment_id)] = (text, comment.ticket_id)
 
    existing = collection.get() #retrieves all the existing documents in ChromaDB
    existing_docs = dict(zip(existing["ids"], existing["documents"])) #creates a dictionary, that connects ID to its document text.

    # Finds documents that exist in ChromaDB but no longer exist in SQL.
    removed = [i for i in existing_docs if i not in current]
    if removed:
        collection.delete(ids=removed)
 
    ids, documents, metadatas = [], [], []
    for comment_id, (text, ticket_id) in current.items():
        if existing_docs.get(comment_id) != text:
            ids.append(comment_id)
            documents.append(text)
            metadatas.append({"ticket_id": ticket_id, "internal_comment_id": int(comment_id)})
    if ids:
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
 
    return len(current)# returns the number of internal comments that were indexed

def search_knowledge_base(query: str, n_results: int = 3):
    if collection.count() == 0:
        return []
    results = collection.query(query_texts=[query], n_results=n_results)#searches chroma w/ users question
    hits = []
    for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
        if dist <= THRESHOLD_DISTANCE:
            hits.append((meta["ticket_id"], doc))
    return hits

@asynccontextmanager # Creates the FastAPI lifespan context manager.
async def lifespan(app: FastAPI):
    #tries to sync the knowledge base on startup.
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
                   "http://localhost:8000", "http://127.0.0.1:8000","http://127.0.0.1:8001"],
    allow_methods=["*"],   #allow GET, POST, Patch etc.
    allow_headers=["*"],   #allow headers like Authorization and Content-Type
)
@app.post("/sync-knowledge-base")
def sync_knowledge_base(db: Session = Depends(get_db)):
    """Rebuilds the knowledge base from InternalComments."""
    count = sync_internal_comments(db) #syncs the internal comments from the database to the knowledge base
    return {"message": f"Synced {count} internal comments indexed."}

# Defines the structure of the data required by the /index-note endpoint.
class NoteIndex(BaseModel):
    internal_comment_id: int

# Creates an endpoint for indexing one internal note.
@app.post("/index-note")
def index_note(data: NoteIndex, x_sync_key: str = Header(None), db: Session = Depends(get_db)):
    """Embeds one internal note right after it is saved (called by main.py)."""
    if not SYNC_KEY or x_sync_key != SYNC_KEY:
        raise HTTPException(status_code=403, detail="Not allowed")
    comment = db.query(InternalComment).filter(
        InternalComment.internal_comment_id == data.internal_comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Note not found")
    ticket = db.query(Ticket).filter(Ticket.ticket_id == comment.ticket_id).first()
    text = build_document(comment, ticket)
    if text:
        collection.upsert(
            ids=[str(comment.internal_comment_id)],
            documents=[text],
            metadatas=[{"ticket_id": comment.ticket_id,
                        "internal_comment_id": comment.internal_comment_id}],
        )
    return {"indexed": bool(text)}

# Creates a GET endpoint for testing knowledge base searches.
@app.get("/search-knowledge-base")
def search_kb(query: str, n_results: int = 5):
    hits = search_knowledge_base(query, n_results)
    return [{"ticket_id": ticket_id, "text": text} for ticket_id, text in hits]

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatRequest(BaseModel):
    question: str = Field(..., max_length=700)
    history: List[ChatMessage] = []


# Creates the main chatbot endpoint.
# The frontend sends the user's question and conversation history here.
@app.post("/chat")
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """Answer a user's question using ONLY past tickets and their internal notes."""
    #helps pick up notes that were added, edited, or deleted.
    try:
        sync_internal_comments(db)
    except Exception as e:
        print("Sync before chat failed, using existing knowledge base:", e)
 
    history_t = list(request.history[-10:]) # Copies the last 10 messages from the conversation history. So that there is no unlimited conversation 
     # Removes assistant messages at the beginning of the history. makes sure the conversation starts with a user message.
    while history_t and history_t[0].role != "user":
        history_t.pop(0)

      # Creates a list containing only the previous user messages.
    prev_user_messages = [m.content for m in history_t if m.role == "user"]
    search_text = " ".join(prev_user_messages[-1:] + [request.question]) #Combines the most recent previous user message with the new question.

     # Searches the knowledge base for the three closest matching documents.
    hits = search_knowledge_base(search_text, n_results=3)#finds the 3 closests entries 

     # Checks whether any relevant documents were found.
    if hits:
        context = "\n\n---\n\n".join(text for _, text in hits)
    else:
        context = "no results found"

      # Adds the current user question to the message history.
    messages = [{"role": m.role, "content": m.content} for m in history_t]
    messages.append({
        "role": "user",
        "content": f"<knowledge_base>\n{context}\n</knowledge_base>\n\nQuestion: {request.question}", # Sends both the knowledge base results and the actual question.
    })
    #asks claude to answer the question using only the knowledge base
    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-5-5",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=messages,
        )

    # Catches errors returned by Anthropic's API.
    except anthropic.APIError as e:
        print("Anthropic error:", repr(e))
        raise HTTPException(status_code=500, detail="Error cant connect to the AI service.")

    # Claude's reply comes as a list of blocks;
    answer = "".join(block.text for block in response.content if block.type == "text")

    # Returns the chatbot's answer and the IDs of the tickets used as sources.
    return {
        "answer": answer,
        "sources": sorted({t for t, _ in hits}),
    }
