from database import SessionLocal
from models import Role

db = SessionLocal()
roles = db.query(Role).all()
for role in roles:
    print(role.role_id, role.role_name)
db.close()