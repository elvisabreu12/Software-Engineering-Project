from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, Boolean
from sqlalchemy.orm import relationship
from database import Base

# Role
class Role(Base):
    __tablename__ = "Roles"  # matches the actual table name in MySQL

    role_id = Column("RoleID", Integer, primary_key=True)
    role_name = Column("RoleName", String(50), nullable=False)
    access_level = Column("AccessLevel", Integer, nullable=False)

# User
class User(Base):
    __tablename__ = "Users"

    user_id = Column("UserID", Integer, primary_key=True)
    role_id = Column("RoleID", Integer, ForeignKey("Roles.RoleID"), nullable=False)
    user_name = Column("UserName", String(100), nullable=False)
    user_email = Column("UserEmail", String(100), nullable=False)
    user_password = Column("UserPassword", String(255), nullable=False)
    user_team = Column("UserTeam", String(50))

    # Lets you go from a user straight to their role: user.role.role_name
    role = relationship("Role")

# Category
class Category(Base):
    __tablename__ = "Categories" 

    category_id = Column("CategoryID", Integer, primary_key=True)
    category_name = Column("CategoryName", String(50), nullable=False)
    category_desc = Column("CategoryDesc", Text)

# Ticket
class Ticket(Base):
    __tablename__ = "Tickets"

    ticket_id = Column("TicketID", Integer, primary_key=True)
    category_id = Column("CategoryID", Integer, ForeignKey("Categories.CategoryID"))
    created_by_user_id = Column("CreatedByUserID", Integer, ForeignKey("Users.UserID"))
    assigned_to_user_id = Column("AssignedToUserID", Integer, ForeignKey("Users.UserID"))
    title = Column("Title", String(100))
    ticket_desc = Column("TicketDesc", Text)
    priority = Column("Priority", String(20))
    status = Column("Status", String(20))
    created = Column("Created", DateTime)
    updated = Column("Updated", DateTime)
    closed = Column("Closed", DateTime)

    # Relationships (foreign_keys says which link each one follows)
    category = relationship("Category")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_user_id])

# Comment
class Comment(Base):
    __tablename__ = "Comments"
    comment_id = Column("CommentID", Integer, primary_key=True)
    ticket_id = Column("TicketID", Integer, ForeignKey("Tickets.TicketID"))
    user_id = Column("UserID", Integer, ForeignKey("Users.UserID"))
    comment_desc = Column("CommentDesc", Text, nullable=False)
    date_created = Column("DateCreated", DateTime)

    # Relationships
    ticket = relationship("Ticket")
    user = relationship("User")

# InternalComment
class InternalComment(Base):
    __tablename__ = "InternalComments"
    internal_comment_id = Column("InternalCommentID", Integer, primary_key=True)
    ticket_id = Column("TicketID", Integer, ForeignKey("Tickets.TicketID"))
    user_id = Column("UserID", Integer, ForeignKey("Users.UserID"))
    internal_comment_desc = Column("InternalCommentDesc", Text)
    date_created = Column("DateCreated", DateTime)

    # Relationships
    ticket = relationship("Ticket")
    user = relationship("User")

# LoginAttempt
class LoginAttempt(Base):
    __tablename__ = "LoginAttempts"
    attempts_id = Column("AttemptsID", Integer, primary_key=True)
    user_id = Column("UserID", Integer, ForeignKey("Users.UserID"))
    user_email = Column("UserEmail", String(100))
    is_success = Column("IsSuccess", Boolean)
    ip_address = Column("IpAddress", String(55))
    attempted_at = Column("AttemptedAt", DateTime)

