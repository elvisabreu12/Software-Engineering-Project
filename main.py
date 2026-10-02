from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Role

app = FastAPI()

@app.get("/hello-world")
def hello_world():
    return {"message": "Welcome to White Rabbit API!"}

@app.get("/test-number2")
def test_number2():
    return {"message": "This is Test Number 2!"}


@app.get("/roles") # defines a GET endpoint at /roles
def get_roles(db: Session = Depends(get_db)): 
    """ 
    Get all roles.
    FastAPI Depends() system automatically calls get_db() to open a database session
    before this function runs, and passes that session in as 'db'.
    """
    roles = db.query(Role).all() # fetch every row from the Roles table
    return roles #Returns the list of Role objects as a JSON response