from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Category, Role, User, Ticket, Comment, InternalComment, LoginAttempt
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

app = FastAPI()


# Pydantic model for creating a new ticket

# This is the list of fields the caller must send. FastAPI checks it automatically,
# so a missing title or text in place of a number is rejected with a clear "ValidationError" before the code runs.

class TicketCreate(BaseModel):
    title: str
    ticket_desc: Optional[str] = None
    priority: str
    category_id: int
    created_by_user_id: int

###
### Endpoints to create new records in the database tables. 
### Each endpoint uses the get_db() dependency to open a database session, 
### and then adds a new record to the appropriate table. The new record is returned as JSON.
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
    db.add(new_ticket) # Adds the new ticket to the database session
    db.commit() # commits the transaction, which inserts the new row into the database
    db.refresh(new_ticket) # refreshes the new_ticket object with the data from the database, including the auto-generated ticket_id
    return {"ticket_id": new_ticket.ticket_id, "status": new_ticket.status} # Returns the new ticket's ID and status as a JSON response


###
### Endpoints to access the database tables. Each endpoint uses the get_db() dependency to open a database session, 
### and then queries the appropriate table. The results are returned as JSON.
###

# Roles
@app.get("/roles") # defines a GET endpoint at /roles
def get_roles(db: Session = Depends(get_db)): 
    """ 
    Get all roles.
    FastAPI Depends() system automatically calls get_db() to open a database session
    before this function runs, and passes that session in as 'db'.
    """
    roles = db.query(Role).all() # fetch every row from the Roles table
    return roles #Returns the list of Role objects as a JSON response

# Users
@app.get("/users")
def get_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    # Build the response by hand so the password column is never sent out
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

# Categories
@app.get("/categories")
def get_categories(db: Session = Depends(get_db)): # defines a GET endpoint at /categories
    categories = db.query(Category).all()
    return categories

# Tickets
@app.get("/tickets")
def get_tickets(db: Session = Depends(get_db)): # defines a GET endpoint at /tickets
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

# Comments
@app.get("/comments")
def get_comments(db: Session = Depends(get_db)): # defines a GET endpoint at /comments
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

# Internal Comments
@app.get("/internal-comments")
def get_internal_comments(db: Session = Depends(get_db)): # defines a GET endpoint at /internal-comments
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

# Login Attempts
@app.get("/login-attempts")
def get_login_attempts(db: Session = Depends(get_db)): # defines a GET endpoint at /login-attempts
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