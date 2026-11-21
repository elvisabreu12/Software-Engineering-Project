# This is the main backend file. It makes the FastAPI app and has every endpoint (login, tickets, comments, profiles, and so on).
# The frontend JS files call these endpoints on port 8000.
import os
import json
# urllib.request is used to send a message to the chatbot server (notify_ragbot below)
import urllib.request
from datetime import datetime
from typing import Optional

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request, BackgroundTasks
# func lets me use database functions in queries, like lower() for emails
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from models import Category, Role, User, Ticket, Comment, InternalComment, LoginAttempt, UserSkill
from pydantic import BaseModel
# assigning.py picks the best agent for a ticket, Sla.py works out the SLA due times, similarity.py finds similar tickets
from assigning import suggest_agent
from Sla import sla_info
from typing import Optional
from datetime import datetime
from security import hash_password, verify_password, create_access_token, decode_access_token
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import similarity


@asynccontextmanager
# The code before yield runs one time when the server starts, so it's a good place to set things up.
async def lifespan(app: FastAPI):
    # The similar-ticket index lives in memory, so rebuild it from the database every time the server starts
    db = SessionLocal()
    try:
        similarity.index_all(db, Ticket)
    except Exception as e:
        print("Could not build the similar-ticket index:", e)
    finally:
        db.close()
    yield

# this makes the app. lifespan runs the startup code above.
app = FastAPI(lifespan=lifespan)

# CORS: the browser blocks the frontend from calling a different address (port) unless the server allows it.
# This list is the pages that are allowed to talk to the backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001",
                   "http://localhost:5500", "http://127.0.0.1:5500",   # VS Code Live Server
                   "http://localhost:8080", "http://127.0.0.1:8080",
                   "null"],                                            # pages opened straight from a file (file://)
    allow_methods=["*"],      # allow GET, POST, Patch etc.
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

# These classes are the shape of the data each endpoint expects to receive. If something is missing, FastAPI sends back an error.
class LoginRequest(BaseModel):
    user_email: str
    user_password: str

class RegisterRequest(BaseModel):
    user_name: str
    user_email: str
    user_password: str

class CommentCreate(BaseModel):
    comment_desc: str

class StatusUpdate(BaseModel):
    status: str

# the new text when someone edits an internal note
class NoteEdit(BaseModel):
    internal_comment_desc: str

# what the similar tickets box sends: the title and description so far, and a ticket to skip
class SimilarQuery(BaseModel):
    title: str
    ticket_desc: Optional[str] = None
    exclude_id: Optional[int] = None

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

# This finds one ticket and checks the person is allowed to see it. Used by almost every ticket endpoint,
# so the access rules are only written once.
def get_ticket_for_user(ticket_id: int, current_user: User, db: Session):
    # look the ticket up by its id (None if it isn't there)
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

#tells the chatbot server (port 8001) to index a new internal note right away.
# If the chatbot is down this only prints a message; saving the note still works.
# note_id is the internal note to index. X-Sync-Key is a password so the chatbot knows the request is from this backend.
def notify_ragbot(note_id: int):
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:8001/index-note",
            data=json.dumps({"internal_comment_id": note_id}).encode(),
            headers={"Content-Type": "application/json",
                     "X-Sync-Key": os.getenv("RAGBOT_SYNC_KEY", "")},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=30)
    except Exception as e:
        print("Could not notify chatbot:", e)
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
    # check the data first, so bad input gets a clear error message
    ticket.title = ticket.title.strip()
    if not ticket.title or len(ticket.title) > 100:
        raise HTTPException(status_code=400, detail="Title is required and must be 100 characters or fewer")
    if ticket.priority not in ("Low", "Medium", "High"):
        raise HTTPException(status_code=400, detail="Priority must be Low, Medium or High")
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
    # add the new ticket to the similarity index so it can show up in future searches
    similarity.index_ticket(new_ticket)

    # auto-assign: ask assigning.py for the best agent based on skills. match is None if nobody fits.
    match = suggest_agent(db, new_ticket)
    if match:
        new_ticket.assigned_to_user_id = match["user_id"]
        db.commit()

    
    return {"ticket_id": new_ticket.ticket_id, "status": new_ticket.status,
            "assigned_to": match["user_name"] if match else None, "matched_skills": match["matched_skills"] if match else [], }  # returns the new ticket's id and status as JSON


# Login
@app.post("/login")
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    # Look up the user by email (None if no match)
    # func.lower on both sides so the email match ignores upper/lower case
    user = db.query(User).filter(func.lower(User.user_email) == data.user_email.strip().lower()).first()

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
    email = data.user_email.strip().lower()
    if db.query(User).filter(func.lower(User.user_email) == email).first():
        # 409 = conflict, because the email is already used
        raise HTTPException(status_code=409, detail="That email is already registered")
    # new accounts always get the End User role, so nobody can sign up as an admin
    end_user_role = db.query(Role).filter(Role.role_name == "End User").first()
    new_user = User(
        role_id=end_user_role.role_id,
        user_name=data.user_name,
        user_email=email,
        user_password=hash_password(data.user_password),
    )
    db.add(new_user)
    db.commit()
    # this reloads the user so we can use the id the database made
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
def add_ticket_internal_comment(ticket_id: int, data: CommentCreate, background_tasks: BackgroundTasks,
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
    background_tasks.add_task(notify_ragbot, note.internal_comment_id)   # index the note in the chatbot right away
    return {"internal_comment_id": note.internal_comment_id, "ticket_id": ticket_id} 

# Edit an internal note (the person who wrote it, or an administrator)
# Only the person who wrote the note or an admin can change it. The note is sent to the chatbot again so it knows the new text.
@app.patch("/tickets/{ticket_id}/internal-comments/{note_id}")
def edit_internal_comment(ticket_id: int, note_id: int, data: NoteEdit, background_tasks: BackgroundTasks,
                          current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_staff(current_user)
    ticket = get_ticket_for_user(ticket_id, current_user, db)
    note = (db.query(InternalComment)
            .filter(InternalComment.internal_comment_id == note_id,
                    InternalComment.ticket_id == ticket_id).first())
    # the note has to exist AND belong to this ticket
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    # not your note and you're not an admin, so no
    if note.user_id != current_user.user_id and current_user.role.access_level < 3:
        raise HTTPException(status_code=403, detail="You can only edit your own notes")
    text = data.internal_comment_desc.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Note can't be empty")
    note.internal_comment_desc = text
    ticket.updated = datetime.now()
    db.commit()
    background_tasks.add_task(notify_ragbot, note.internal_comment_id)   # the chatbot re-indexes the new text
    return {"internal_comment_id": note.internal_comment_id, "ticket_id": ticket_id}

# Changes a ticket's status (staff only)
@app.patch("/tickets/{ticket_id}/status")
# Receives the ticket ID, new status information, logged-in user, and database session
def update_status(ticket_id: int, data: StatusUpdate,
                  current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Makes sure the current user has staff permissions
    require_staff(current_user)
    # Checks if the requested status is one of the allowed options
    if data.status not in ("Open", "In Progress", "Resolved", "Closed"):
        raise HTTPException(status_code=400, detail="Unknown status") #error if the status is not recognized
    t = get_ticket_for_user(ticket_id, current_user, db) # Finds the ticket the user is allowed to access
    t.status = data.status   # Updates the ticket with the new status
    t.updated = datetime.now() # Records the date and time when the ticket was updated
    # Records the closing date if the ticket is resolved or closed
    # Otherwise, clears the closing date
    t.closed = datetime.now() if data.status in ("Resolved", "Closed") else None
    db.commit() #saves changes  
    # update the index so the similarity search sees the new status
    similarity.index_ticket(t)
    return {"ticket_id": t.ticket_id, "status": t.status}
# The "similar tickets already solved" box on the new ticket page calls this while someone types.
# Staff see open and solved tickets with all the info. End users only see solved ones, with just the basic info.
@app.post("/similar-tickets")
def similar_tickets(q: SimilarQuery, current_user: User = Depends(get_current_user)):
    # staff = True for agents and admins
    staff = current_user.role.access_level >= 2
    # found = the similar tickets (include_open is True only for staff)
    found = similarity.find_similar(q.title, q.ticket_desc, q.exclude_id, include_open=staff)
    return found if staff else [{"ticket_id": f["ticket_id"], "title": f["title"],
                                 "status": f["status"], "similarity": f["similarity"]} for f in found]

# Groups of similar open tickets = a possible bigger problem (staff only)
# The incident detection. hours is how far back to look and min_size is how many similar tickets make an incident.
@app.get("/incidents")
def incidents(hours: int = 24, min_size: int = 3,
              current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_staff(current_user)
    return similarity.find_incidents(db, Ticket, hours, min_size)
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

# The staff and employees pages use this list
# Users (admins only)
@app.get("/users")
def get_users(
    current_user: User = Depends(get_current_user),   # reads the token and gives us the logged-in user (401 if not logged in)
    db: Session = Depends(get_db),
):
    # Only Administrators (access level 3) may list users
    if current_user.role.access_level < 3:
        raise HTTPException(status_code=403, detail="You don't have permission to do this")  # 403 = logged in, but not allowed

    # get everyone from the Users table
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
def get_tickets(
    current_user: User = Depends(get_current_user),   # must be logged in (401 if not)
    db: Session = Depends(get_db),
):
    # start with all tickets, then filter below depending on the role
    query = db.query(Ticket)
    # End Users (level 1) only see tickets they created; agents and admins see all
    if current_user.role.access_level < 2:
        query = query.filter(Ticket.created_by_user_id == current_user.user_id)
    tickets = query.order_by(Ticket.ticket_id.desc()).all()   #newest first
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
            "created_by_id": t.created_by_user_id,
            "assigned_to": t.assigned_to.user_name if t.assigned_to else None,
            "assigned_to_id": t.assigned_to_user_id,
            # ** puts everything from sla_info (due time, state, minutes left) into this dictionary
            **sla_info(t),
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
        "created_by_id": t.created_by_user_id,
        "assigned_to": t.assigned_to.user_name if t.assigned_to else None,
        "assigned_to_id": t.assigned_to_user_id,
        **sla_info(t),
    }

# Comments (normal, not internal)
#read the normal comments of one ticket( the requester and IT can both see these)
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
        "user_id": c.user_id,                                # lets the page show Edit on your own notes
        "user": c.user.user_name if c.user else None,
        "role": c.user.role.role_name if c.user else None,
        "internal_comment_desc": c.internal_comment_desc,
        "date_created": c.date_created,
    } for c in comments] 

# Admins can see every login try, including the failed ones
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


###
### SLA, assignment and queue
###

# the id of the agent to assign. None means take the assignment off.
class AssignUpdate(BaseModel):
    user_id: Optional[int] = None      # None = unassign


# One ticket as a small dictionary. The queue uses it so the code isn't repeated.
def ticket_row(t):
    return {
        "ticket_id": t.ticket_id,
        "title": t.title,
        "priority": t.priority,
        "status": t.status,
        "created": t.created,
        "category": t.category.category_name if t.category else None,
        "created_by": t.created_by.user_name if t.created_by else None,
        "assigned_to": t.assigned_to.user_name if t.assigned_to else None,
        **sla_info(t),
    }

# Assign a ticket to an agent/admin (staff only). Agents can only assign to themselves; admins to anyone.
@app.patch("/tickets/{ticket_id}/assign")
def assign_ticket(ticket_id: int, data: AssignUpdate,
                  current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_staff(current_user)
    t = get_ticket_for_user(ticket_id, current_user, db)
    if data.user_id is not None:
        # target = the person the ticket is being given to
        target = db.query(User).filter(User.user_id == data.user_id).first()
        if target is None or target.role.access_level < 2:
            raise HTTPException(status_code=400, detail="Tickets can only be assigned to agents or administrators")
        if current_user.role.access_level < 3 and target.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Only administrators can assign to someone else")
    # if user_id is None this clears the assignment
    t.assigned_to_user_id = data.user_id
    t.updated = datetime.now()
    db.commit()
    return {"ticket_id": t.ticket_id, "assigned_to_id": t.assigned_to_user_id}

#open tickets assigned to the logged in agent
@app.get("/queue")
def my_queue(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_staff(current_user)
    tickets = (db.query(Ticket)
               .filter(Ticket.assigned_to_user_id == current_user.user_id,
                       Ticket.status.in_(["Open", "In Progress"]))
               .all())
    # turn each ticket into a dictionary
    rows = [ticket_row(t) for t in tickets]
    # sort by due time, the one due soonest goes first. Tickets with no due time go to the end (datetime.max).
    rows.sort(key=lambda r: r["sla_due"] or datetime.max)
    return rows

# Counts how many tickets are in each SLA state. compliance_pct is the % of finished tickets that were done on time.
@app.get("/sla-summary")
def sla_summary(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_staff(current_user)
    # one counter per state, all start at 0
    counts = {"on_track": 0, "at_risk": 0, "breached": 0, "met": 0, "missed": 0}
    for t in db.query(Ticket).all():
        counts[sla_info(t)["sla_state"]] += 1
    # finished = tickets that are done, either on time or late
    finished = counts["met"] + counts["missed"]
    # the if/else avoids dividing by zero when no tickets are finished
    counts["compliance_pct"] = round(100 * counts["met"] / finished) if finished else None
    return counts


###
### Profiles (name, email, role, skills)
###
# the only levels that are allowed
SKILL_LEVELS = ("Beginner", "Intermediate", "Expert")

# both are optional so someone can change just their name or just their email
class ProfileUpdate(BaseModel):
    user_name: Optional[str] = None
    user_email: Optional[str] = None

class SkillItem(BaseModel):
    skill: str
    level: str

# a list of skills, each one with a name and a level
class SkillsUpdate(BaseModel):
    skills: list[SkillItem]


# Builds the profile info (with skills) for a user. Used by a few endpoints so it's only written once.
def profile_dict(u: User, db: Session):
    skills = db.query(UserSkill).filter(UserSkill.user_id == u.user_id).order_by(UserSkill.skill).all()
    return {
        "user_id": u.user_id,
        "user_name": u.user_name,
        "user_email": u.user_email,
        "role": u.role.role_name,
        "access_level": u.role.access_level,
        "skills": [{"skill": s.skill, "level": s.level} for s in skills],
    }

# Staff and the owner can see a profile. An end user can also see the profile of the agent assigned to one of their tickets.
def can_view_profile(viewer: User, target: User, db: Session) -> bool:
    if viewer.role.access_level >= 2 or viewer.user_id == target.user_id:
        return True
    # looks for a ticket made by the viewer and assigned to the target. If there is one, they are allowed.
    return db.query(Ticket).filter(Ticket.created_by_user_id == viewer.user_id,
                                   Ticket.assigned_to_user_id == target.user_id).first() is not None


# the logged in user's own profile
@app.get("/profile")
def my_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return profile_dict(current_user, db)


# someone else's profile, only if can_view_profile says it's ok
@app.get("/users/{user_id}/profile")
def user_profile(user_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.user_id == user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not can_view_profile(current_user, target, db):
        raise HTTPException(status_code=403, detail="You don't have access to this profile")
    return profile_dict(target, db)


# Edit your own name and email (role is set by an administrator)
@app.patch("/profile")
def update_profile(data: ProfileUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.user_name is not None:
        name = data.user_name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name cannot be empty")
        current_user.user_name = name
    if data.user_email is not None:
        email = data.user_email.strip().lower()
        if "@" not in email:
            raise HTTPException(status_code=400, detail="Enter a valid email address")
        # make sure nobody else already uses this email
        taken = db.query(User).filter(func.lower(User.user_email) == email, User.user_id != current_user.user_id).first()
        if taken:
            raise HTTPException(status_code=400, detail="That email is already in use")
        current_user.user_email = email
    db.commit()
    return profile_dict(current_user, db)


# Replace a person's skill list. Agents edit their own; admins can edit any agent's.
@app.put("/users/{user_id}/skills")
def set_skills(user_id: int, data: SkillsUpdate,
               current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_staff(current_user)
    if current_user.role.access_level < 3 and user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Only administrators can edit someone else's skills")
    target = db.query(User).filter(User.user_id == user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if target.role.access_level < 2:
        raise HTTPException(status_code=400, detail="Skills are only for agents and administrators")
    # cleaned is the list we will save. seen remembers names already used so there are no duplicate skills.
    cleaned, seen = [], set()
    for item in data.skills:
        name = item.skill.strip()
        if name and name.lower() not in seen:
            if item.level not in SKILL_LEVELS:
                raise HTTPException(status_code=400, detail="Level must be Beginner, Intermediate or Expert")
            seen.add(name.lower())
            cleaned.append((name[:50], item.level))
    # delete the old skills, then add the new list. This is how "replace" works.
    db.query(UserSkill).filter(UserSkill.user_id == user_id).delete()
    for name, level in cleaned:
        db.add(UserSkill(user_id=user_id, skill=name, level=level))
    db.commit()
    return profile_dict(target, db)


# Who would the skill match pick for this ticket? (staff only; used by the ticket page)
# the ticket page shows this so an admin can see who the skills would pick
@app.get("/tickets/{ticket_id}/suggested-assignee")
def suggested_assignee(ticket_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_staff(current_user)
    t = get_ticket_for_user(ticket_id, current_user, db)
    return suggest_agent(db, t)      # null when nobody has a matching skill

#change password 
class PasswordChange(BaseModel):
    current_password: str
    new_password: str

# The person has to type their current password first, so someone using a computer left logged in can't change it.
@app.post("/profile/password")
def change_password(data: PasswordChange, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(data.current_password, current_user.user_password):
        raise HTTPException(status_code=400, detail="Your current password is incorrect")
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="The new password must be at least 8 characters")
    if data.new_password == data.current_password:
        raise HTTPException(status_code=400, detail="The new password must be different from the current one")
    # save the hash of the new password, never the password itself
    current_user.user_password = hash_password(data.new_password)
    db.commit()
    return {"detail": "Password updated"}