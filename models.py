from sqlalchemy import Column, Integer, String
from database import Base

class Role(Base):
    __tablename__ = "Roles"  # matches the actual table name in MySQL

    role_id = Column("RoleID", Integer, primary_key=True)
    role_name = Column("RoleName", String(50), nullable=False)