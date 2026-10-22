-- seed_data.sql
-- Test data for TicketingDB so every teammate's local database matches.
-- Run AFTER Ticketing_Database.sql (which already inserts the 3 Roles).
-- Run it ONCE on a fresh database; running it twice creates duplicates.
--
-- Test logins (all three use the same password: Test1234!)
--   admin@test.com  -> Administrator (access level 3)
--   user@test.com   -> End User      (access level 1)
--   agent@test.com  -> Agent         (access level 2)

USE TicketingDB;

-- Categories
INSERT INTO Categories (CategoryName, CategoryDesc) VALUES
('Hardware', 'Laptops, monitors, printers and other devices'),
('Software', 'Application installs, crashes and licenses'),
('Network', 'Wi-Fi, VPN and connectivity problems'),
('Account Access', 'Passwords, logins and permissions');

-- Users (RoleID: 1 = End User, 2 = Agent, 3 = Administrator)
-- The long value is a bcrypt hash of the test password "Test1234!"
INSERT INTO Users (RoleID, UserName, UserEmail, UserPassword, UserTeam) VALUES
(3, 'Test Admin', 'admin@test.com', '$2b$12$GeQOvEa0VZr9Bf/r0Z5ccuMEAh68xhD/7N0R5I1nejcqPMpzXT/ZK', 'IT'),
(1, 'Test User',  'user@test.com',  '$2b$12$GeQOvEa0VZr9Bf/r0Z5ccuMEAh68xhD/7N0R5I1nejcqPMpzXT/ZK', 'Sales'),
(2, 'Test Agent', 'agent@test.com', '$2b$12$GeQOvEa0VZr9Bf/r0Z5ccuMEAh68xhD/7N0R5I1nejcqPMpzXT/ZK', 'IT');

-- Tickets (CategoryID 1 = Hardware, 3 = Network; user ids: 1 = Admin, 2 = User, 3 = Agent)
INSERT INTO Tickets (CategoryID, CreatedByUserID, AssignedToUserID, Title, TicketDesc, Priority, Status, Created) VALUES
(1, 1, NULL, 'Laptop will not turn on', 'Black screen after update', 'High', 'Open', NOW()),
(1, 1, NULL, 'Printer jammed', 'Third floor', 'Medium', 'Open', NOW()),
(3, 2, 3,    'Cannot connect to VPN', 'Error appears after entering credentials', 'High', 'In Progress', NOW());

-- Comments (visible to the ticket creator)
INSERT INTO Comments (TicketID, UserID, CommentDesc, DateCreated)
VALUES (1, 1, 'Have you tried holding the power button for 10 seconds?', NOW());

-- Internal comments (agents/admins only)
INSERT INTO InternalComments (TicketID, UserID, InternalCommentDesc, DateCreated)
VALUES (1, 1, 'Likely a battery issue, check warranty.', NOW());

-- Login attempts
INSERT INTO LoginAttempts (UserID, UserEmail, IsSuccess, IpAddress)
VALUES (1, 'admin@test.com', TRUE, '127.0.0.1');