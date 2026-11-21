
"""Duplicate-ticket and incident detection using ChromaDB similarity.
Everything runs locally and costs nothing. If chromadb is not installed the
functions simply return empty results, so the rest of the site keeps working."""
# This file finds tickets that look alike. It's used for the "similar tickets" box on the new ticket page
# and for spotting possible incidents (lots of people reporting the same thing).
import re
from datetime import datetime, timedelta
 
try:
    # ChromaDB is a vector database. It turns text into numbers so we can find text with a similar meaning.
    import chromadb
    # _col is the collection (like a table) that holds all the tickets. "cosine" is how it measures how close two texts are.
    _col = chromadb.Client().get_or_create_collection(
        name="all_tickets", metadata={"hnsw:space": "cosine"})
except Exception as e:                      # chromadb missing or broken
    print("Similarity search disabled:", e)
    _col = None
 
# tickets further apart than this are not counted as similar
MAX_DIST = 0.45      # cosine distance. Smaller = stricter. Tune with real tickets.
# statuses that mean the ticket is finished
DONE = ("resolved", "closed")
 
 
# True if the ticket is still open. The (status or "") is there so a missing status doesn't crash it.
def is_open(status):
    return (status or "").lower() not in DONE
 
 
# the text we give Chroma for a ticket: the title and the description together
def ticket_text(t):
    return f"{t.title}. {t.ticket_desc or ''}".strip()
 
 
def index_ticket(t):
    """Add or refresh one ticket in the index (call after create / status change)."""
    # if chromadb isn't working there is nothing to do
    if _col is None:
        return
    try:
        # upsert = add the ticket, or update it if it's already there (same id)
        _col.upsert(
            ids=[str(t.ticket_id)],
            documents=[ticket_text(t)],
            metadatas=[{
                "ticket_id": t.ticket_id,
                "title": t.title or "",
                "status": t.status or "",
                "category": t.category.category_name if t.category else "",
            }],
        )
    except Exception as e:
        print("Could not index ticket:", e)
 
 
def index_all(db, Ticket):
    """The index lives in memory, so rebuild it whenever the server starts."""
    for t in db.query(Ticket).all():
        index_ticket(t)
 
 
# This looks for tickets close to the title and description someone is typing.
# exclude_id skips a ticket itself, include_open=False only gives back finished tickets (solved ones), n is the max number of results.
def find_similar(title, desc=None, exclude_id=None, include_open=True, n=5):
    # if the index is empty there is nothing to compare with
    if _col is None or _col.count() == 0:
        return []
    # ask Chroma for the closest tickets. n+1 because one of them might be the ticket itself and gets thrown out.
    res = _col.query(query_texts=[f"{title}. {desc or ''}"],
                     n_results=min(n + 1, _col.count()))
    out = []
    # m is the info about a result (metadata) and d is its distance. Smaller distance = more similar.
    for m, d in zip(res["metadatas"][0], res["distances"][0]):
        # close enough, and not the ticket we told it to skip
        close_enough = d <= MAX_DIST and m["ticket_id"] != exclude_id
        # if we only want solved tickets, skip the open ones
        allowed = include_open or not is_open(m["status"])
        if close_enough and allowed:
            # 1 - distance turns it into a similarity score (closer to 1 = more alike)
            out.append({**m, "similarity": round(1 - d, 2)})
    return out[:n]
 
 
# ---- Shared-cause signals: words/phrases that, when most tickets in a group
# mention them, point to a common cause. Add your own to the list. ----
# If most tickets in a group have the same word from this list, it probably means the same cause.
SIGNALS = [
    "windows update", "update", "windows 11", "windows 10", "macos", "patch", "upgrade",
    "freez", "frozen", "hang", "crash", "blue screen", "slow", "restart", "reboot",
    "vpn", "wifi", "wi-fi", "network", "internet", "outlook", "email", "teams", "zoom",
    "excel", "office", "printer", "login", "password", "locked out", "server", "shared drive",
    "laptop", "desktop", "monitor", "dell", "lenovo", "hp ", "macbook",
]
# nicer names to show for some of the signals
LABELS = {"freez": "freezing", "frozen": "frozen", "hang": "hanging", "crash": "crashes", "hp ": "HP"}
 
# Device or asset names such as PC-1042, LT 233, WKS-12
# a regex (pattern) that finds device names like PC-1042 or LT 233. re.I means ignore upper/lower case.
DEVICE_RE = re.compile(r"\b(?:pc|lt|wks|ws|laptop|asset)[-_ ]?\d{2,}\b", re.I)
 
 
# all the words in a ticket, lowercase, for searching
def _text(t):
    return f"{t.title or ''} {t.ticket_desc or ''}".lower()
 
 
# Checks which signal words show up in at least 60% of the tickets (share=0.6).
# Example: 4 of 5 tickets say "windows update".
def shared_signals(tickets, share=0.6):
    """Phrases mentioned by at least `share` of the tickets (e.g. 4 of 5 say 'windows update')."""
    out = []
    for sig in SIGNALS:
        # n = how many tickets contain this signal
        n = sum(1 for t in tickets if sig in _text(t))
        # needs at least 2 tickets, and at least the share of the group
        if n >= max(2, share * len(tickets)):
            out.append({"signal": LABELS.get(sig, sig.strip()), "count": n})
    # "update" is redundant when "windows update" is already listed
    if any(o["signal"] == "windows update" for o in out):
        out = [o for o in out if o["signal"] != "update"]
    # biggest counts first, and only keep the top 4
    return sorted(out, key=lambda x: -x["count"])[:4]
 
 
# finds all the device names in the tickets. A set is used so a device isn't listed twice.
def devices_in(tickets):
    found = set()
    for t in tickets:
        found.update(m.upper().replace(" ", "-") for m in DEVICE_RE.findall(f"{t.title or ''} {t.ticket_desc or ''}"))
    return sorted(found)
 
 
# This puts a group of ticket ids into one incident dictionary that the frontend can show.
# kind is "similar" or "category_spike", members are the ticket ids, by_id is a dictionary to look tickets up.
def _build_group(kind, members, by_id, reason_prefix):
    tickets = [by_id[i] for i in members]
    cats = [t.category.category_name for t in tickets if t.category]
    # cat is the category that shows up the most in the group
    cat = max(set(cats), key=cats.count) if cats else None
    sigs = shared_signals(tickets)
    # first = the oldest ticket's time, latest = the newest one's
    first = min(t.created for t in tickets)
    latest = max(t.created for t in tickets)
    n = len(tickets)
    reason = f"{n} open tickets{' in ' + cat if cat else ''}"
    if sigs:
        top = sigs[0]
        reason += f"; {top['count']} of {n} mention \"{top['signal']}\""
    return {
        "type": kind,                       # "similar" or "category_spike"
        # 5 or more tickets is high, otherwise medium
        "severity": "high" if n >= 5 else "medium",
        "size": n,
        "sample_title": tickets[0].title,
        "category": cat,
        "reason": reason,
        "shared_signals": sigs,
        "devices": devices_in(tickets),
        "first_reported": first,
        "latest": latest,
        "ticket_ids": sorted(members),
        "tickets": [{"ticket_id": t.ticket_id, "title": t.title} for t in sorted(tickets, key=lambda x: x.ticket_id)],
    }
 
 
# This looks at tickets from the last 24 hours (hours=24) and groups the open ones into possible incidents.
# min_size=3 means a group needs at least 3 tickets.
def find_incidents(db, Ticket, hours=24, min_size=3):
    """Possible larger problems, found two ways (no machine learning):
    1. similar text  - 3+ open tickets that Chroma says describe the same thing
    2. category spike - 3+ open tickets in the same category within the window"""
    # since = the start of the time window
    since = datetime.now() - timedelta(hours=hours)
    # recent = open tickets created inside the window
    recent = [t for t in db.query(Ticket).filter(Ticket.created >= since).all() if is_open(t.status)]
    by_id = {t.ticket_id: t for t in recent}
    # seen keeps the ids already put in a group, groups is the list we return
    seen, groups = set(), []
 
    if _col is not None and _col.count() > 0:
        for t in recent:
            if t.ticket_id not in seen:
                # for each ticket, ask Chroma for others that are similar to it
                res = _col.query(query_texts=[ticket_text(t)], n_results=min(20, _col.count()))
                # keep only the similar ones that are recent, close enough, and not already in a group
                members = [int(i) for i, d in zip(res["ids"][0], res["distances"][0])
                           if d <= MAX_DIST and int(i) in by_id and int(i) not in seen]
                # make sure the ticket itself is in the group
                if t.ticket_id not in members:
                    members.append(t.ticket_id)
                # big enough to count as an incident
                if len(members) >= min_size:
                    seen.update(members)
                    groups.append(_build_group("similar", members, by_id, ""))
 
    # Category spikes among tickets not already in a similar-text group
    # group the left over tickets by category
    by_cat = {}
    for t in recent:
        if t.ticket_id not in seen and t.category_id is not None:
            by_cat.setdefault(t.category_id, []).append(t.ticket_id)
    for members in by_cat.values():
        if len(members) >= min_size:
            groups.append(_build_group("category_spike", members, by_id, ""))
 
    # high severity first, then the biggest groups first
    return sorted(groups, key=lambda g: (g["severity"] != "high", -g["size"]))
 