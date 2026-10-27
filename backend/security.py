import bcrypt
import os
from datetime import datetime, timedelta, timezone
import jwt  # PyJWT: creates and checks login tokens.
from dotenv import load_dotenv 

# load everything in .env into the environment.
load_dotenv()     
# the private key used to sign tokens.                         
SECRET_KEY = os.getenv("SECRET_KEY")    
# the signing method; must match when creating and checking.   
ALGORITHM = "HS256" 
# how long a token stays valid.                        
TOKEN_MINUTES = 60                          



# This function takes a plain password and returns a hashed version of it using bcrypt.
# The hashed password is safe to store in a database.
def hash_password(password: str) -> str:
    """Turn a plain password into a bcrypt hash that is safe to store."""
    # password.encode() turns the text into bytes.
    # bcrypt.gensalt() generates a random salt for the hash.
    # bcrypt.hashpw() hashes the password with the salt.
    # .decode() turns the bytes back into text so it can be stored in the database
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


# This function takes a plain password and a hashed password, and checks if the plain password matches the hash.
def verify_password(password: str, hashed: str) -> bool:
    """Check a typed password against the stored hash."""
    # password.encode() turns the text into bytes.
    # hashed.encode() turns the stored hash into bytes.
    # bcrypt.checkpw() checks if the password matches the hash.
    return bcrypt.checkpw(password.encode(), hashed.encode())


# This function creates a signed token that says "this is user "UserName" " and expires in 60 minutes.
def create_access_token(user_id: int) -> str:
    """Make a signed token that says 'this is user X' and expires in 60 minutes."""
    # the payload = the information written inside the token.
    # "subject": who the token is about (the user id, as text).
    # "expires": the current time plus 60 minutes, after which the token is no longer valid.
    payload = {                             
        "sub": str(user_id),                
        "exp": datetime.now(timezone.utc)   
               + timedelta(minutes=TOKEN_MINUTES),  
    }
    # Sign the payload with the secret key using HS256 and return the token string.
    # The server does not store it; the user sends it back with each request.
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# This function takes a token and checks if it is valid and not expired. If it is valid, it returns the user id inside the token. 
# If it is invalid or expired, it returns None.
def decode_access_token(token: str):
    """Return the user id inside a valid token, or None if it's fake or expired."""
    # try this, and if the library raises an error, jump to except.
    # Recompute the signature with the secret key and compare it with the token's.
    # Also checks "exp". Raises an error if the token was changed or has expired.
    try:                                    
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # read the user id from the payload, text back to a number.
        return int(payload["sub"])   
    # any token problem: fake, tampered with, or expired.
    # None means "not logged in".
    except jwt.PyJWTError:                  
        return None                         
