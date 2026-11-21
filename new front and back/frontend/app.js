// app.js - shared code for every page.
// This file is the ONLY place that knows how to talk to the backend.

// Where the FastAPI backend is running
const API = "http://127.0.0.1:8000";

// Shortcut for document.getElementById
const $ = (id) => document.getElementById(id);

// ---------- Light / dark theme (chosen on the Settings page, saved in this browser) ----------
const THEME_KEY = "wr_theme";                       // "light", "dark" or "system"
// localStorage is a small storage inside the browser that is still there after closing the tab. The try/catch is there in case the browser blocks it.
function getTheme() { try { return localStorage.getItem(THEME_KEY) || "light"; } catch (e) { return "light"; } }
// works out if the page should be dark or light, then sets data-theme on the <html> tag. dark.css reacts to that.
function applyTheme() {
  const t = getTheme();
  const dark = t === "dark" || (t === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
}
function setTheme(t) { try { localStorage.setItem(THEME_KEY, t); } catch (e) {} applyTheme(); }
(function loadTheme() {
  // dark.css only does something when <html data-theme="dark">
  const link = document.createElement("link");
  link.rel = "stylesheet"; link.href = "dark.css";
  document.head.appendChild(link);
  applyTheme();
  // "Match my device" follows the computer if it switches between light and dark
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", applyTheme);
})();

// ---------- The login token (saved in the browser) ----------
const TOKEN_KEY = "wr_token";
function getToken() { try { return localStorage.getItem(TOKEN_KEY); } catch (e) { return null; } }
//added for AI
// the chatbot history is kept in sessionStorage (it goes away when the tab closes). This key is its name.
const CHAT_KEY = "hd-history";
function clearChat() { try { sessionStorage.removeItem(CHAT_KEY); } catch (e) {} }
//
function setToken(t) { try { localStorage.setItem(TOKEN_KEY, t); } catch (e) {} clearChat(); }  // clear the chat history when logging in or out
function clearToken() { try { localStorage.removeItem(TOKEN_KEY); } catch (e) {} clearChat(); }  // clear the chat history when logging in or out

// ---------- api(): one function that sends every request ----------
// Example: await api("/tickets")
//          await api("/login", { method: "POST", body: JSON.stringify({...}) })
// async/await lets the code wait for the server's answer without freezing the page.
async function api(path, options = {}) {
  // get the saved login token, if there is one
  const token = getToken();
  // headers = extra info sent with the request. Content-Type says we are sending JSON.
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = "Bearer " + token;   // proves who we are

  // fetch sends the request. If it fails completely, the backend is probably not running.
  let response;
  try {
    response = await fetch(API + path, { ...options, headers });
  } catch (e) {
    throw new Error("Could not reach the server. Is the backend running?");
  }

  // turn the answer into JSON. If there is nothing to read (like an empty answer) data just stays null.
  let data = null;
  try { data = await response.json(); } catch (e) {}

  if (!response.ok) {
    // Token missing/expired: go back to the login page
    if (response.status === 401 && token && path !== "/login") {
      clearToken();
      window.location.href = "loginpage.html";
    }
    // build an error message. FastAPI puts it in data.detail, as text or as a list of problems.
    let message = "Request failed (" + response.status + ")";
    if (data && typeof data.detail === "string") message = data.detail;
    else if (data && Array.isArray(data.detail)) message = data.detail.map((d) => d.msg).join("; ");
    throw new Error(message);
  }
  return data;
}

// ---------- initPage(): run at the top of every page that needs a login ----------
// minLevel: 1 = anyone logged in, 2 = agents and admins, 3 = admins only
// Returns the logged-in user (from GET /me), or null if we are redirecting away.
async function initPage(minLevel = 1) {
  // no token means not logged in, so go to the login page
  if (!getToken()) {
    window.location.href = "loginpage.html";
    return null;
  }
  try {
    // ask the backend who is logged in. If the token is bad, api() sends us to the login page.
    const me = await api("/me");
    // not high enough for this page, so go to the user dashboard
    if (me.access_level < minLevel) {
      window.location.href = "user_Dash.html";
      return null;
    }
    // show the name and role in the sidebar
    $("me-name").textContent = me.user_name;
    $("me-role").textContent = me.role;
    initNav(me);
    // "Home" goes to the dashboard that matches the role
    $("nav-home").href = me.access_level >= 3 ? "admin_Dash.html" : "user_Dash.html";
    // logging out removes the token and goes back to the homepage
    $("logout").onclick = (e) => {
      e.preventDefault();
      clearToken();
      window.location.href = "homepage.html";
    };
    return me;
  } catch (e) {
    // something went wrong, so show the error message on the page
    const area = document.querySelector(".content");
    if (area) area.innerHTML = '<div class="msg error">' + esc(e.message) + "</div>";
    return null;
  }
}

// ---------- Small display helpers ----------

// Makes text safe to put inside HTML
// Very important when putting text from users into innerHTML. It turns characters like < and > into safe text so nobody can sneak in a script (XSS).
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// "2h ago", "3d ago"
// turns a date into something short like "2h ago". diff is how many seconds ago it was.
function timeAgo(iso) {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return Math.floor(diff / 60) + "m ago";
  if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
  return Math.floor(diff / 86400) + "d ago";
}

// Groups the free-text status into open / progress / done
// The status is plain text, so this puts it into one of 3 groups. That way the colors and the stat cards are easier.
function statusGroup(status) {
  const v = (status || "").toLowerCase();
  if (v.includes("progress")) return "progress";
  if (v.includes("resolved") || v.includes("closed")) return "done";
  return "open";
}

// returns a colored label for the priority. If the priority is unknown it uses the Low color.
function priorityPill(p) {
  const cls = { High: "pill-high", Medium: "pill-medium", Low: "pill-low" }[p] || "pill-low";
  return '<span class="pill ' + cls + '">' + esc(p || "-") + "</span>";
}

function statusPill(s) {
  return '<span class="pill pill-' + statusGroup(s) + '">' + esc(s || "-") + "</span>";
}

// Counts for the stat cards
// counts how many tickets are in each group for the stat cards at the top. filter keeps only the ones that match.
function ticketStats(list) {
  return {
    total: list.length,
    open: list.filter((t) => statusGroup(t.status) === "open").length,
    progress: list.filter((t) => statusGroup(t.status) === "progress").length,
    done: list.filter((t) => statusGroup(t.status) === "done").length,
  };
}

// Builds a ticket table. showPeople = true adds the "Created by" column.
function ticketTable(list, showPeople) {
  if (!list.length) return '<div class="empty">No tickets to show.</div>';
  // the top row of the table. The Created by column is only added if showPeople is true.
  const head =
    "<tr><th>ID</th><th>Title</th><th>Category</th><th>Priority</th><th>Status</th>" +
    (showPeople ? "<th>Created by</th>" : "") + "<th>Created</th></tr>";
  // makes one table row for each ticket, then join puts them together as one string
  const rows = list.map((t) =>
    "<tr>" +
      '<td class="muted">#' + esc(t.ticket_id) + "</td>" +
      '<td><a class="row-link" href="ticket.html?id=' + esc(t.ticket_id) + '">' + esc(t.title) + "</a></td>" +
      "<td>" + esc(t.category || "-") + "</td>" +
      "<td>" + priorityPill(t.priority) + "</td>" +
      "<td>" + statusPill(t.status) + "</td>" +
      (showPeople ? "<td>" + esc(t.created_by || "-") + "</td>" : "") +
      '<td class="muted">' + esc(timeAgo(t.created)) + "</td>" +
    "</tr>").join("");
  return '<div class="table-wrap"><table class="tbl"><thead>' + head + "</thead><tbody>" + rows + "</tbody></table></div>";
}

// ---------- Sidebar: Tickets and By Type submenus ----------
async function initNav(me) {
  // the sidebar menus that can open and close (Tickets and By Type)
  const groups = document.querySelectorAll(".nav-group");
  if (!groups.length) return;
  // Staff-only links (All Tickets) stay hidden for end users
  document.querySelectorAll(".staff-only").forEach((el) => { el.hidden = me.access_level < 2; });
  // Admin-only links (Staff, Employees) stay hidden for everyone else
  document.querySelectorAll(".admin-only").forEach((el) => { el.hidden = me.access_level < 3; });
  groups.forEach((group) => {
    const parent = group.querySelector(".nav-parent");
    // clicking the menu title opens or closes it. On small screens it just goes to the page instead.
    parent.onclick = (e) => {
      if (window.innerWidth <= 900) return;          // small screens: just open the page
      e.preventDefault();
      parent.setAttribute("aria-expanded", group.classList.toggle("open"));
    };
  });
  // Fill "By Type" with the real categories (keeps the default three if the request fails)
  try {
    // get the categories from the backend and make a link for each one. encodeURIComponent makes the name safe for a URL.
    const cats = await api("/categories");
    if (cats.length) {
      $("type-list").innerHTML = cats.map((c) =>
        '<a href="TIcket_Q.html?view=type&type=' + encodeURIComponent(c.category_name) + '">' + esc(c.category_name) + "</a>").join("");
    }
  } catch (e) {}
  highlightNav();
  initInPlaceNav();
}

// Marks the sub-link for the page we are on, and opens the right group
// looks at the URL to see which sidebar link matches the page we are on, and makes it active
function highlightNav() {
  const params = new URLSearchParams(location.search);
  const onList = location.pathname.endsWith("TIcket_Q.html");
  const view = params.get("view") || "all";
  const type = params.get("type");
  document.querySelectorAll(".subnav a").forEach((a) => {
    const u = new URL(a.href).searchParams;
    a.classList.toggle("active", onList && u.get("view") === view && (view !== "type" || u.get("type") === type));
  });
  if (onList && view === "type") {
    const tickets = $("nav-group"), types = $("type-group");
    tickets.classList.remove("open"); types.classList.add("open");
    $("nav-tickets").setAttribute("aria-expanded", "false"); $("nav-types").setAttribute("aria-expanded", "true");
  }
}

// ---------- Dashboards: the sidebar's ticket links open right here instead of jumping to another page ----------
// Only runs on pages whose <body> has data-inplace (the two dashboards). The ticket list / New Ticket form
// (TIcket_Q.html, in its "embed" mode without sidebar) is shown inside the dashboard, and Home brings the dashboard back.
// embed=1 tells TIcket_Q.html to hide its own sidebar and header, since it is showing inside the dashboard.
function initInPlaceNav() {
  if (!document.body.hasAttribute("data-inplace")) return;
  const main = document.querySelector(".main-container");
  const content = main.querySelector(".content");
  const title = main.querySelector(".header-title");
  const homeTitle = title.textContent;
  const home = $("nav-home");
  // an iframe is a page inside a page. This is the box where the ticket list shows up.
  const frame = document.createElement("iframe");
  frame.className = "view-frame"; frame.title = "Tickets"; frame.hidden = true;
  main.appendChild(frame);

  const subLinks = () => document.querySelectorAll(".subnav a");
  // highlights the link that is open, and the sidebar group it is in
  function mark(link) {
    subLinks().forEach((x) => x.classList.toggle("active", x === link));
    if (home) home.classList.toggle("active", !link);
    if (link) {
      const group = link.closest(".nav-group");
      if (group) { group.classList.add("open"); const p = group.querySelector(".nav-parent"); if (p) p.setAttribute("aria-expanded", "true"); }
    }
  }
  // go back to the normal dashboard: hide the iframe and show the dashboard content again
  function showHome() {
    frame.hidden = true; frame.removeAttribute("src");
    content.hidden = false; title.textContent = homeTitle; mark(null);
  }
  // show a ticket page inside the iframe and change the title at the top
  function open(href) {
    const q = new URL(href, location.href).searchParams;
    const link = [...subLinks()].find((x) => x.getAttribute("href") === href);
    title.textContent = link ? link.textContent : q.get("view") === "new" ? "New Ticket" : "Tickets";
    content.hidden = true; frame.hidden = false;
    frame.src = href + (href.includes("?") ? "&" : "?") + "embed=1";
    mark(link || null);
    if (!link && home) home.classList.remove("active");
  }

  // one click listener for the whole page. It catches clicks on links: Home shows the dashboard, ticket links open in the iframe,
  // and everything else works normally.
  document.addEventListener("click", (e) => {
    if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey) return;
    const a = e.target.closest("a"); if (!a) return;
    const href = a.getAttribute("href") || "";
    if (a === home) { e.preventDefault(); showHome(); return; }
    if (a.classList.contains("nav-parent") || !href.startsWith("TIcket_Q.html")) return;
    e.preventDefault(); open(href);
  });
}

// ---------- Possible incidents (GET /incidents, agents and admins) ----------
// Groups of open tickets from the last 24 hours that look like one shared problem.
// builds the HTML for the list of incidents. Each group is one box with its severity, reason, shared words, devices and tickets.
function incidentsHtml(list) {
  if (!list.length) return '<div class="empty">No possible incidents right now. Nothing is clustering in the last 24 hours.</div>';
  return list.map((g) => {
    // high = true if this incident is high severity (it gets a red style)
    const high = g.severity === "high";
    // the little tags for the shared words and the devices, with || [] so it doesn't break if they are missing
    const signals = (g.shared_signals || []).map((s) => '<span class="chip">' + esc(s.signal) + " &times; " + esc(s.count) + "</span>").join("");
    const devices = (g.devices || []).map((d) => '<span class="chip">' + esc(d) + "</span>").join("");
    return '<div class="incident' + (high ? " high" : "") + '">' +
      '<div class="incident-top"><span class="pill ' + (high ? "pill-high" : "pill-medium") + '">' + (high ? "High" : "Medium") + " severity</span>" +
      '<span class="chip">' + (g.type === "similar" ? "Similar tickets" : "Category spike") + "</span>" +
      '<span class="muted">' + esc(g.size) + " tickets &middot; first " + esc(timeAgo(g.first_reported)) + " &middot; latest " + esc(timeAgo(g.latest)) + "</span></div>" +
      "<h4>" + esc(g.reason) + "</h4>" +
      '<div class="incident-sub">Example: ' + esc(g.sample_title) + (g.category ? " &middot; " + esc(g.category) : "") + "</div>" +
      (signals ? '<div class="incident-row"><small>Shared words</small>' + signals + "</div>" : "") +
      (devices ? '<div class="incident-row"><small>Devices</small>' + devices + "</div>" : "") +
      '<div class="incident-row"><small>Tickets</small>' +
      (g.tickets || []).map((t) => '<a class="row-link" href="ticket.html?id=' + encodeURIComponent(t.ticket_id) + '">#' + esc(t.ticket_id) + " " + esc(t.title) + "</a>").join("") +
      "</div></div>";
  }).join("");
}

// ---------- Click a notification to dismiss it ----------
// Works for the green/red message boxes ("Ticket submitted", "Profile saved", errors...) and the incident banner.
document.addEventListener("click", (e) => {
  const box = e.target.closest(".msg, .incident-banner");
  if (!box || e.target.closest("button, a")) return;     // buttons and links inside still do their own thing
  box.hidden = true;
  if (box.id === "incident-banner") {
    try { sessionStorage.setItem("wr_incident_dismissed", box.dataset.key || "1"); } catch (err) {}
  }
});