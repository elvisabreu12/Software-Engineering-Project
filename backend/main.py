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
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000","http://localhost:3001", "http://127.0.0.1:3001"],  # where the React app runs
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

# Pydantic model for login request
class LoginRequest(BaseModel):
    user_email: str
    user_password: str

# Pydantic model for registering a new user
class RegisterRequest(BaseModel):
    user_name: str
    user_email: str
    user_password: str
 
# Pydantic model for creating a new comment(both internal and normal)
class CommentCreate(BaseModel):
    comment_desc: str

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

# Helper function: finds a ticket and checks the logged-in user is allowed to see it 
def get_ticket_for_user(ticket_id: int, current_user: User, db: Session):
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")  # 404 = doesn't exist
    # End Users (level 1) can only open their own tickets; agents and admins can open any
    if current_user.role.access_level < 2 and ticket.created_by_user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="You don't have access to this ticket")  # 403 = exists, but not yours
    return ticket


# Helper function: stops End Users from using staff-only endpoints
def require_staff(current_user: User):
    if current_user.role.access_level < 2:
        raise HTTPException(status_code=403, detail="You don't have permission to do this")

###
### Endpoints to create new records in the database tables. 
### Each endpoint uses the get_db() dependency to open a database session, 
### and then adds a new record to the appropriate table. The new record is returned as JSON.
###

# Create a new ticket
@app.post("/tickets")
def create_ticket(
    ticket: TicketCreate,                              # the data the frontend sent (title, description, priority, category)
    current_user: User = Depends(get_current_user),    # reads the token and gives us the logged-in user (401 if not logged in)
    db: Session = Depends(get_db),                     # gives us a database session
):
    # Check the category exists first, so a bad id gives a clear error instead of a database crash
    if not db.query(Category).filter(Category.category_id == ticket.category_id).first():
        raise HTTPException(status_code=400, detail="Unknown category")  # 400 = the request itself was bad

    new_ticket = Ticket(
        title=ticket.title,
        ticket_desc=ticket.ticket_desc,
        priority=ticket.priority,
        category_id=ticket.category_id,
        created_by_user_id=current_user.user_id,       # comes from the token now, so nobody can create tickets as someone else
        status="Open",                                 # every new ticket starts as Open
        created=datetime.now(),                        # set the time in code, because the ORM sends NULL otherwise
    )
    db.add(new_ticket)       # adds the new ticket to the database session
    db.commit()              # commits the transaction, which inserts the new row into the database
    db.refresh(new_ticket)   # reloads the object from the database, including the auto-generated ticket_id
    return {"ticket_id": new_ticket.ticket_id, "status": new_ticket.status}  # returns the new ticket's id and status as JSON


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

# Register a new user, everyone who registers will become an end user.
@app.post("/register", status_code=201)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    if len(data.user_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if db.query(User).filter(User.user_email == data.user_email).first():
        raise HTTPException(status_code=409, detail="That email is already registered")
    end_user_role = db.query(Role).filter(Role.role_name == "End User").first()
    new_user = User(
        role_id=end_user_role.role_id,
        user_name=data.user_name,
        user_email=data.user_email,
        user_password=hash_password(data.user_password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"user_id": new_user.user_id, "user_name": new_user.user_name, "user_email": new_user.user_email}

# Add a normal comment
@app.post("/tickets/{ticket_id}/comments", status_code=201)   # 201 = created
def add_ticket_comment(ticket_id: int, data: CommentCreate,
                       current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ticket = get_ticket_for_user(ticket_id, current_user, db) # make sure this user may see the ticket
    text = data.comment_desc.strip()                       # removes spaces at the start and end
    if not text:
        raise HTTPException(status_code=400, detail="Comment can't be empty")
    now = datetime.now() # set the time in code, because the ORM sends NULL otherwise
    new_comment = Comment( # create a new Comment object with the data from the request and the current user
        ticket_id=ticket_id,
        user_id=current_user.user_id,                      # who wrote it comes from the token, never from the page
        comment_desc=text,
        date_created=now,                                  # set in code because the ORM sends NULL otherwise
    )
    ticket.updated = now                                   # a new comment counts as an update to the ticket
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)                                # loads the auto-generated comment_id
    return {"comment_id": new_comment.comment_id, "ticket_id": ticket_id}

# Add an internal note (agents and admins only)
@app.post("/tickets/{ticket_id}/internal-comments", status_code=201) # 201 = created
def add_ticket_internal_comment(ticket_id: int, data: CommentCreate,
                                current_user: User = Depends(get_current_user), db: Session = Depends(get_db)): # reads the token and gives us the logged-in user (401 if not logged in)
    require_staff(current_user) # stops End Users from using this endpoint (403 if not allowed)
    ticket = get_ticket_for_user(ticket_id, current_user, db) # make sure this user may see the ticket
    text = data.comment_desc.strip() # removes spaces at the start and end
    if not text:
        raise HTTPException(status_code=400, detail="Comment can't be empty") # 400 = the request itself was bad
    now = datetime.now() # set the time in code, because the ORM sends NULL otherwise
    note = InternalComment( # create a new InternalComment object with the data from the request and the current user
        ticket_id=ticket_id,
        user_id=current_user.user_id,
        internal_comment_desc=text,
        date_created=now,
    )
    ticket.updated = now # a new internal comment counts as an update to the ticket
    db.add(note)
    db.commit()
    db.refresh(note)
    return {"internal_comment_id": note.internal_comment_id, "ticket_id": ticket_id} 

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

# Users (admins only)
@app.get("/users")
def get_users(
    current_user: User = Depends(get_current_user),   # reads the token and gives us the logged-in user (401 if not logged in)
    db: Session = Depends(get_db),
):
    # Only Administrators (access level 3) may list users
    if current_user.role.access_level < 3:
        raise HTTPException(status_code=403, detail="You don't have permission to do this")  # 403 = logged in, but not allowed

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

# Tickets (list)
@app.get("/tickets")
def get_tickets(current_user: User = Depends(get_current_user),    # reads the token; 401 if not logged in
    db: Session = Depends(get_db),):

    query = db.query(Ticket)
    # End Users (level 1) only get the tickets they created; agents and admins get all of them.
    if current_user.role.access_level < 2:
        query = query.filter(Ticket.created_by_user_id == current_user.user_id)
    tickets = query.order_by(Ticket.ticket_id.desc()).all()   # newest first
    result = []
    for t in tickets:
        result.append({
            "ticket_id": t.ticket_id,
            "title": t.title,
            "description": t.ticket_desc,
            "priority": t.priority,
            "status": t.status,
            "created": t.created,
            "updated": t.updated,
            "category": t.category.category_name if t.category else None,
            "created_by": t.created_by.user_name if t.created_by else None,
            "assigned_to": t.assigned_to.user_name if t.assigned_to else None,
        })
    return result

# One ticket's details (for the ticket detail page)
@app.get("/tickets/{ticket_id}")   # {ticket_id} in the URL becomes the ticket_id parameter
def get_ticket(ticket_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = get_ticket_for_user(ticket_id, current_user, db)   # 404 / 403 handled inside the helper
    return {
        "ticket_id": t.ticket_id,
        "title": t.title,
        "description": t.ticket_desc,
        "priority": t.priority,
        "status": t.status,
        "created": t.created,
        "updated": t.updated,
        "closed": t.closed,
        "category": t.category.category_name if t.category else None,
        "created_by": t.created_by.user_name if t.created_by else None,
        "assigned_to": t.assigned_to.user_name if t.assigned_to else None,
    }

# Comments (normal, not internal)
# Read the normal comments of one ticket (the requester and IT can both see these)
@app.get("/tickets/{ticket_id}/comments")
def get_ticket_comments(ticket_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_ticket_for_user(ticket_id, current_user, db)       # make sure this user may see the ticket
    comments = (db.query(Comment)
                .filter(Comment.ticket_id == ticket_id)    # only this ticket's comments
                .order_by(Comment.comment_id)              # oldest first, like a chat
                .all())
    return [{
        "comment_id": c.comment_id,
        "ticket_id": c.ticket_id,
        "user": c.user.user_name if c.user else None,
        "role": c.user.role.role_name if c.user else None,  # lets the page label who is IT and who is the requester
        "comment_desc": c.comment_desc,
        "date_created": c.date_created,
    } for c in comments]

# Internal Comments
# Read the internal notes of one ticket (agents and admins only)
@app.get("/tickets/{ticket_id}/internal-comments")
def get_ticket_internal_comments(ticket_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_staff(current_user)                            # End Users stop here with a 403
    get_ticket_for_user(ticket_id, current_user, db) # make sure this user may see the ticket
    comments = (db.query(InternalComment) # query the InternalComments table
                .filter(InternalComment.ticket_id == ticket_id) # only this ticket's internal comments
                .order_by(InternalComment.internal_comment_id) # oldest first, like a chat
                .all())
    return [{
        "internal_comment_id": c.internal_comment_id,
        "ticket_id": c.ticket_id,
        "user": c.user.user_name if c.user else None,
        "role": c.user.role.role_name if c.user else None,
        "internal_comment_desc": c.internal_comment_desc,
        "date_created": c.date_created,
    } for c in comments] 


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
