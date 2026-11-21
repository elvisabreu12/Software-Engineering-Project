"""SLA (service level agreement) rules for WHT_RBT.

Nothing here touches the database schema: the due time is worked out from the
ticket's Priority and Created time, so no migration is needed.

Change SLA_HOURS to change the targets for your presentation.
"""
from datetime import datetime, timedelta

# How many hours IT has to RESOLVE a ticket, by priority
# SLA_HOURS is a dictionary: the priority is the key and the value is the hours allowed
SLA_HOURS = {"High": 4, "Medium": 24, "Low": 72}
# used when a ticket has a priority that isn't in the list above
DEFAULT_HOURS = 24

# A ticket is "at risk" once less than this share of its time is left
AT_RISK_SHARE = 0.25


def sla_info(ticket, now=None):
    """Returns a dict with the SLA target, due time and state for one ticket.

    state is one of:
      on_track  - open, plenty of time left
      at_risk   - open, under 25% of the time left
      breached  - open and past the due time
      met       - finished before the due time
      missed    - finished after the due time
    """
    # if no time is passed in, use the current time (passing one in is handy for testing)
    now = now or datetime.now()
    # look up the hours for this ticket's priority, or use the default if it isn't found
    hours = SLA_HOURS.get(ticket.priority, DEFAULT_HOURS)
    # no created time means we can't work out a due time, so just say on_track
    if ticket.created is None:
        return {"sla_hours": hours, "sla_due": None, "sla_state": "on_track", "sla_minutes_left": None}

    # due time = when it was created + the hours it is allowed
    due = ticket.created + timedelta(hours=hours)
    # Resolved and Closed tickets are done, so we judge them by when they finished
    finished = ticket.status in ("Resolved", "Closed")

    if finished:
        # the finish time is the closed time. If that's empty, use the updated time, then now.
        end = ticket.closed or ticket.updated or now
        state = "met" if end <= due else "missed"
        minutes_left = None
    else:
        # (due - now) is a time difference. total_seconds() // 60 turns it into whole minutes.
        minutes_left = int((due - now).total_seconds() // 60)
        if now > due:
            state = "breached"
        # at risk = less than 25% of the allowed time is left (AT_RISK_SHARE)
        elif (due - now) < timedelta(hours=hours * AT_RISK_SHARE):
            state = "at_risk"
        else:
            state = "on_track"

    return {
        "sla_hours": hours,
        "sla_due": due,
        "sla_state": state,
        "sla_minutes_left": minutes_left,   # negative when already late
    }