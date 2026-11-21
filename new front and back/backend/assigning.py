from sqlalchemy.orm import Session

from models import User, Ticket, UserSkill

# How many points each skill level is worth when we compare agents
LEVEL_POINTS = {"Beginner": 1, "Intermediate": 2, "Expert": 3}
# Tickets with these statuses count as still being worked on (used to see how busy an agent is)
OPEN_STATUSES = ("Open", "In Progress")


# This puts the category, title and description into one lowercase string.
# That way we can check if an agent's skill word shows up anywhere in the ticket.
def _ticket_text(ticket: Ticket) -> str:
    parts = [
        ticket.category.category_name if ticket.category else "",
        ticket.title or "",
        ticket.ticket_desc or "",
    ]
    return " ".join(parts).lower()


# This function picks the best agent for a ticket. It is used for the suggested assignee on the ticket page
# and for auto-assigning when a ticket is created. It compares the agents' skills against the ticket text.
def suggest_agent(db: Session, ticket: Ticket):
    """Returns {"user_id", "user_name", "score", "matched_skills", "open_tickets"} or None."""
    # text is the ticket's words, lowercase so the match isn't case sensitive
    text = _ticket_text(ticket)
    # only keep staff, so access level 2 (agent) or 3 (admin). End users can't be assigned tickets.
    agents = [u for u in db.query(User).all() if u.role.access_level >= 2]

    # best keeps the strongest candidate so far, None means no one matched yet
    best = None
    for agent in agents:
        # get all the skills this agent has listed
        skills = db.query(UserSkill).filter(UserSkill.user_id == agent.user_id).all()
        # matched is the agent's skills that are actually mentioned in the ticket (for example "vpn" in the title)
        matched = [s for s in skills if s.skill.strip().lower() in text]
        # agents with no matching skill are skipped
        if matched:
            # add up the points for every matched skill (Beginner 1, Intermediate 2, Expert 3). .get(..., 1) uses 1 if the level is something unexpected.
            score = sum(LEVEL_POINTS.get(s.level, 1) for s in matched)
            # count how many open tickets this agent already has, so we can see how busy they are
            open_count = (db.query(Ticket)
                          .filter(Ticket.assigned_to_user_id == agent.user_id,
                                  Ticket.status.in_(OPEN_STATUSES))
                          .count())
            # everything we want to send back about this agent
            candidate = {
                "user_id": agent.user_id,
                "user_name": agent.user_name,
                "score": score,
                "matched_skills": [s.skill for s in matched],
                "open_tickets": open_count,
            }
            # if there is no best yet, this one wins. The minus on open_count makes fewer tickets count as better.
            # Higher score wins; on a tie, fewer open tickets wins
            if best is None or (score, -open_count) > (best["score"], -best["open_tickets"]):
                best = candidate
    # returns the winner as a dictionary, or None if nobody matched
    return best