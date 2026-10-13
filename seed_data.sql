-- seed_data.sql
-- Test data for TicketingDB so every teammate's local database matches.
-- Run AFTER Ticketing_Database.sql (which already inserts the 3 Roles).
-- Run it ONCE on a fresh database; running it twice creates duplicates.

USE TicketingDB;

-- Categories
INSERT INTO Categories (CategoryName, CategoryDesc) VALUES
('Hardware', 'Laptops, monitors, printers and other devices'),
('Software', 'Application installs, crashes and licenses'),
('Network', 'Wi-Fi, VPN and connectivity problems'),
('Account Access', 'Passwords, logins and permissions');

-- Users (RoleID 3 = Administrator)
-- NOTE: 'placeholder' is not a real password hash. These will be replaced
-- once login and password hashing are built.
INSERT INTO Users (RoleID, UserName, UserEmail, UserPassword, UserTeam)
VALUES (3, 'Test Admin', 'admin@test.com', 'placeholder', 'IT');

-- Tickets (CategoryID 1 = Hardware, CreatedByUserID 1 = Test Admin)
INSERT INTO Tickets (CategoryID, CreatedByUserID, Title, TicketDesc, Priority, Status, Created)
VALUES
(1, 1, 'Laptop will not turn on', 'Black screen after update', 'High', 'Open', NOW()),
(1, 1, 'Printer jammed', 'Third floor', 'Medium', 'Open', NOW());

-- Comments (visible to the ticket creator)
INSERT INTO Comments (TicketID, UserID, CommentDesc, DateCreated)
VALUES (1, 1, 'Have you tried holding the power button for 10 seconds?', NOW());

-- Internal comments (agents/admins only)
INSERT INTO InternalComments (TicketID, UserID, InternalCommentDesc, DateCreated)
VALUES (1, 1, 'Likely a battery issue, check warranty.', NOW());

-- Login attempts
INSERT INTO LoginAttempts (UserID, UserEmail, IsSuccess, IpAddress)
VALUES (1, 'admin@test.com', TRUE, '127.0.0.1');
