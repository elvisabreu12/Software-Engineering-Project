import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()  # reads the .env file

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

if __name__ == "__main__":
    try:
        connection = engine.connect() # connect to the database
        print("✅ Successfully connected to the database!")
        connection.close()
    except Exception as e:
        print("❌ Connection failed:", e)

""" Dependency to get a single database session """
def get_db():
    db = SessionLocal() #Opens a new database session
    try:
        yield db # Yields the database session to the caller
    finally:
        db.close() # Closes the database session after the caller is done using it