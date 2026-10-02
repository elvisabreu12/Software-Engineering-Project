CREATE DATABASE IF NOT EXISTS TicketingDB;

USE TicketingDB;

CREATE TABLE Roles (
	RoleID INT AUTO_INCREMENT PRIMARY KEY,
    RoleName VARCHAR(50) NOT NULL
);

CREATE TABLE Users (
	UserID INT AUTO_INCREMENT PRIMARY KEY,
    RoleID INT NOT NULL,
    UserName VARCHAR(100) NOT NULL,
    UserEmail VARCHAR(100) NOT NULL,
    UserPassword VARCHAR(255) NOT NULL,
    UserTeam VARCHAR(50)
);

ALTER TABLE Users
ADD CONSTRAINT FK_Users_Roles
FOREIGN KEY (RoleID)
REFERENCES Roles(RoleID);

CREATE TABLE Categories (
	CategoryID INT AUTO_INCREMENT PRIMARY KEY,
    CategoryName VARCHAR(50) NOT NULL,
    CategoryDesc TEXT
);

CREATE TABLE Tickets (
	TicketID INT AUTO_INCREMENT PRIMARY KEY,
    CategoryID INT,
    CreatedByUserID INT,
    AssignedToUserID INT,
    Title VARCHAR(100),
    TicketDesc TEXT,
    Priority VARCHAR(20),
    Status VARCHAR(20),
    Created DATETIME,
    Updated DATETIME,
    Closed DATETIME,
    
    CONSTRAINT FK_Category
    FOREIGN KEY (CategoryID)
    REFERENCES Categories(CategoryID),
    
    CONSTRAINT FK_CreatedByUser
    FOREIGN KEY (CreatedByUserID)
    REFERENCES Users(UserID),
    
    CONSTRAINT FK_AssignedToUserID
    FOREIGN KEY (AssignedToUserID)
    REFERENCES Users(UserID)
);

CREATE TABLE Comments (
	CommentID INT AUTO_INCREMENT PRIMARY KEY,
    TicketID INT,
    UserID INT,
    CommentDesc TEXT NOT NULL,
    DateCreated DATETIME,
    
    CONSTRAINT FK_TicketID
    FOREIGN KEY (TicketID)
    REFERENCES Tickets(TicketID),
    
    CONSTRAINT FK_UserID
    FOREIGN KEY (UserID)
    REFERENCES Users(UserID)
);

CREATE TABLE InternalComments (
	InternalCommentID INT AUTO_INCREMENT PRIMARY KEY,
    TicketID INT,
    UserID INT,
    InternalCommentDesc TEXT,
    DateCreated DATETIME,
    
    CONSTRAINT FK_InternalCommentTicket
    FOREIGN KEY (TicketID)
    REFERENCES Tickets(TicketID),
    
    CONSTRAINT FK_InternalCommentUser
    FOREIGN KEY (UserID)
    REFERENCES Users(UserID)
);

CREATE TABLE LoginAttempts (
	AttemptsID INT AUTO_INCREMENT PRIMARY KEY,
    UserID INT,
    UserEmail VARCHAR(100),
    IsSuccess BOOLEAN,
    IpAddress VARCHAR(55),
    
    CONSTRAINT FK_LoginAttempts_UserID
    FOREIGN KEY (UserID)
    REFERENCES Users(UserID)
);

INSERT INTO Roles(RoleName) VALUES ('End User'), ('Agent'), ('Administrator');