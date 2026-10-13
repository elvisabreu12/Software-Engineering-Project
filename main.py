from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Category, Role, User, Ticket, Comment, InternalComment, LoginAttempt
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import chromadb

app = FastAPI()

# ChromaDB setup
chroma_client = chromadb.Client()
collection = chroma_client.create_collection(name="resolved_tickets")

# Pydantic model for creating a new ticket
class TicketCreate(BaseModel):
    title: str
    ticket_desc: Optional[str] = None
    priority: str
    category_id: int
    created_by_user_id: int

###
### ChromaDB Functions
###

def store_resolved_ticket(ticketID: int, Title: str, InternalCommentID: str):
    collection.add(
        ids=[str(ticketID)],
        documents=[InternalCommentID],
        metadatas=[{"Title": Title, "ticketID": ticketID}]
    )
    return {"status": "Ticket stored in knowledge base"}

def search_knowledge_base(query: str, n_results: int = 5):
    """Search the knowledge base for similar resolved tickets"""
    results = collection.query(
        query_texts=[query],
        n_results=n_results
    )
    return results

###
### Endpoints to create new records
###

@app.post("/tickets")
def create_ticket(ticket: TicketCreate, db: Session = Depends(get_db)):
    new_ticket = Ticket(
        title=ticket.title,
        ticket_desc=ticket.ticket_desc,
        priority=ticket.priority,
        category_id=ticket.category_id,
        created_by_user_id=ticket.created_by_user_id,
        status="Open",
        created=datetime.now(),
    )
    db.add(new_ticket)
    db.commit()
    db.refresh(new_ticket)
    return {"ticket_id": new_ticket.ticket_id, "status": new_ticket.status}

###
### Endpoints to access the database tables
###

@app.get("/roles")
def get_roles(db: Session = Depends(get_db)): 
    roles = db.query(Role).all()
    return roles

@app.get("/users")
def get_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [
        {
            "user_id": u.user_id,
            "user_name": u.user_name,
            "user_email": u.user_email,
            "user_team": u.user_team,
            "role": u.role.role_name,
        }
        for u in users
    ]

@app.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    categories = db.query(Category).all()
    return categories

@app.get("/tickets")
def get_tickets(db: Session = Depends(get_db)):
    tickets = db.query(Ticket).all()
    result = []
    for t in tickets:
        result.append({
            "ticket_id": t.ticket_id,
            "title": t.title,
            "description": t.ticket_desc,
            "priority": t.priority,
            "status": t.status,
            "created": t.created,
            "category": t.category.category_name if t.category else None,
            "created_by": t.created_by.user_name if t.created_by else None,
            "assigned_to": t.assigned_to.user_name if t.assigned_to else None,
        })
    return result

@app.get("/comments")
def get_comments(db: Session = Depends(get_db)):
    comments = db.query(Comment).all()
    result = []
    for c in comments:
        result.append({
            "comment_id": c.comment_id,
            "ticket_id": c.ticket_id,
            "user": c.user.user_name if c.user else None,
            "comment_desc": c.comment_desc,
            "date_created": c.date_created,
        })
    return result

@app.get("/internal-comments")
def get_internal_comments(db: Session = Depends(get_db)):
    comments = db.query(InternalComment).all()
    result = []
    for c in comments:
        result.append({
            "internal_comment_id": c.internal_comment_id,
            "ticket_id": c.ticket_id,
            "user": c.user.user_name if c.user else None,
            "internal_comment_desc": c.internal_comment_desc,
            "date_created": c.date_created,
        })
    return result

@app.get("/login-attempts")
def get_login_attempts(db: Session = Depends(get_db)):
    attempts = db.query(LoginAttempt).all()
    result = []
    for a in attempts:
        result.append({
            "attempts_id": a.attempts_id,
            "user_id": a.user_id,
            "user_email": a.user_email,
            "is_success": a.is_success,
            "ip_address": a.ip_address,
            "attempted_at": a.attempted_at,
        })
    return result

@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    """Get a single tickets information"""
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()

    if not ticket:
        return {"Error": "No ticket found"}

    return {
        "ticket_id": ticket.ticket_id,
        "title": ticket.title,
        "description": ticket.ticket_desc,
        "priority": ticket.priority,
        "status": ticket.status,
        "created": ticket.created,
        "updated": ticket.updated,
        "closed": ticket.closed,
        "category": ticket.category.category_name if ticket.category else None,
        "created_by": ticket.created_by.user_name if ticket.created_by else None,
        "assigned_to": ticket.assigned_to.user_name if ticket.assigned_to else None,
    }

###
### ChromaDB Endpoints
###

@app.post("/sync-resolved-tickets/")
def sync_resolved_tickets(db: Session = Depends(get_db)):
    """Syncs all completed tickets from SQL database to ChromaDB"""
    try:
        solutions = db.query(InternalComment).all()
        
        count = 0
        for solution in solutions:
            ticket = db.query(Ticket).filter(Ticket.ticket_id == solution.ticket_id).first()

            if ticket:
                store_resolved_ticket(
                    ticketID=ticket.ticket_id,
                    Title=ticket.title,
                    InternalCommentID=solution.internal_comment_desc
                )
                count += 1

        return {"status": f"Synced {count} resolved tickets to ChromaDB"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/search-knowledge-base/")
def search_kb(query: str, n_results: int = 5):
    return search_knowledge_base(query, n_results)
