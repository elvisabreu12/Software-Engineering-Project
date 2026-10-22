from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database import get_db
from models import Category, Role, User, Ticket, Comment, InternalComment, LoginAttempt
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from security import verify_password, create_access_token, decode_access_token
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # where the React app runs
    allow_methods=["*"],      # allow GET, POST, etc.
    allow_headers=["*"],      # allow headers like Authorization and Content-Type
)


# Pydantic model for creating a new ticket

# This is the list of fields the caller must send. FastAPI checks it automatically,
# so a missing title or text in place of a number is rejected with a clear "ValidationError" before the code runs.

class TicketCreate(BaseModel):
    title: str
    ticket_desc: Optional[str] = None
    priority: str
    category_id: int
    created_by_user_id: int

class LoginRequest(BaseModel):
    user_email: str
    user_password: str

# create the "token reader" once; endpoints use it through Depends(...)
bearer_scheme = HTTPBearer()


# This function takes the token from the request header, checks if it is valid and not expired, and returns the logged-in User object. 
# If the token is invalid or expired, it raises a 401 Unauthorized error.
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    # FastAPI runs bearer_scheme first, pulls the token out of the request
    # header, and puts it in "credentials". If no token is sent, the request is rejected.
    db: Session = Depends(get_db),
    # a database session, handed over the same way as in your other endpoints
):
    """Turn the token in the request into the logged-in User, or reject with 401."""
    user_id = decode_access_token(credentials.credentials)
    # credentials.credentials is the token text itself;
    # decode_access_token returns the user id inside it, or None if it's fake/expired

    if user_id is None:
        # the token is bad, so stop here and send back a 401 Unauthorized error
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.user_id == user_id).first()
    # look in the Users table for the row whose id matches; first() gives one user or None

    if user is None:
        # the token was valid but that user no longer exists (e.g. deleted), so reject
        raise HTTPException(status_code=401, detail="User not found")

    return user
    # everything checked out: hand the full User object to whoever asked for it



###
### Endpoints to create new records in the database tables. 
### Each endpoint uses the get_db() dependency to open a database session, 
### and then adds a new record to the appropriate table. The new record is returned as JSON.
###

# Create a new ticket
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

# Login
@app.post("/login")
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    # Look up the user by email (None if no match)
    user = db.query(User).filter(User.user_email == data.user_email).first()

    # Success only if the user exists AND the password matches the hash
    success = user is not None and verify_password(data.user_password, user.user_password)

    # Record the attempt, successful or not
    attempt = LoginAttempt(
        user_id=user.user_id if user else None,
        user_email=data.user_email,
        is_success=success,
        ip_address=request.client.host,
        attempted_at=datetime.now(),
    )
    db.add(attempt)
    db.commit()

    # Reject if it failed
    if not success:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Return safe info (never the password hash)
    return {
        "user_id": user.user_id,
        "user_name": user.user_name,
        "user_email": user.user_email,
        "role": user.role.role_name,
        "access_level": user.role.access_level,
        "access_token": create_access_token(user.user_id),
        "token_type": "bearer",
    }

###
### Endpoints to access the database tables. Each endpoint uses the get_db() dependency to open a database session, 
### and then queries the appropriate table. The results are returned as JSON.
###

# Get the logged-in user's info
@app.get("/me")
# GET request at /me
def read_me(current_user: User = Depends(get_current_user)):
    # Depends(get_current_user) runs the function above before this one starts.
    # If it rejects the request, this code never runs. If it succeeds, current_user
    # is the logged-in User.
    return {
        "user_id": current_user.user_id,                 # the user's id
        "user_name": current_user.user_name,             # their name
        "role": current_user.role.role_name,             # role name through the relationship (e.g. "Administrator")
        "access_level": current_user.role.access_level,  # the number (1 = End User, 2 = Agent, 3 = Administrator)
    }
    # the password hash is left out on purpose


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
def get_internal_comments(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)): # defines a GET endpoint at /internal-comments
    # End Users (level 1) are not allowed to see internal notes
    if current_user.role.access_level < 2:
        raise HTTPException(status_code=403, detail="You don't have permission to do this")
    
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
def get_login_attempts(current_user: User = Depends(get_current_user),db: Session = Depends(get_db)): # defines a GET endpoint at /login-attempts
    # Only Administrators (level 3) are allowed to see login attempts
    if current_user.role.access_level < 3:
        raise HTTPException(status_code=403, detail="You don't have permission to do this")
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