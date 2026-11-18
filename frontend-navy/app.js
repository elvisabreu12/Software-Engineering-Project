// app.js - shared code for every page.
// This file is the ONLY place that knows how to talk to the backend.

// Where the FastAPI backend is running
const API = "http://127.0.0.1:8000";

// Shortcut for document.getElementById
const $ = (id) => document.getElementById(id);

// ---------- The login token (saved in the browser) ----------
const TOKEN_KEY = "wr_token";
function getToken() { try { return localStorage.getItem(TOKEN_KEY); } catch (e) { return null; } }
//added for AI
const CHAT_KEY = "hd-history";
function clearChat() { try { sessionStorage.removeItem(CHAT_KEY); } catch (e) {} }
//
function setToken(t) { try { localStorage.setItem(TOKEN_KEY, t); } catch (e) {} }
function clearToken() { try { localStorage.removeItem(TOKEN_KEY); } catch (e) {} }

// ---------- api(): one function that sends every request ----------
// Example: await api("/tickets")
//          await api("/login", { method: "POST", body: JSON.stringify({...}) })
async function api(path, options = {}) {
  const token = getToken();
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = "Bearer " + token;   // proves who we are

  let response;
  try {
    response = await fetch(API + path, { ...options, headers });
  } catch (e) {
    throw new Error("Could not reach the server. Is the backend running?");
  }

  let data = null;
  try { data = await response.json(); } catch (e) {}

  if (!response.ok) {
    // Token missing/expired: go back to the login page
    if (response.status === 401 && token && path !== "/login") {
      clearToken();
      window.location.href = "loginpage.html";
    }
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
  if (!getToken()) {
    window.location.href = "loginpage.html";
    return null;
  }
  try {
    const me = await api("/me");
    if (me.access_level < minLevel) {
      window.location.href = "user_Dash.html";
      return null;
    }
    $("me-name").textContent = me.user_name;
    $("me-role").textContent = me.role;
    initNav(me);
    // "Home" goes to the dashboard that matches the role
    $("nav-home").href = me.access_level >= 3 ? "admin_Dash.html" : "user_Dash.html";
    $("logout").onclick = (e) => {
      e.preventDefault();
      clearToken();
      window.location.href = "homepage.html";
    };
    return me;
  } catch (e) {
    const area = document.querySelector(".content");
    if (area) area.innerHTML = '<div class="msg error">' + esc(e.message) + "</div>";
    return null;
  }
}

// ---------- Small display helpers ----------

// Makes text safe to put inside HTML
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// "2h ago", "3d ago"
function timeAgo(iso) {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return Math.floor(diff / 60) + "m ago";
  if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
  return Math.floor(diff / 86400) + "d ago";
}

// Groups the free-text status into open / progress / done
function statusGroup(status) {
  const v = (status || "").toLowerCase();
  if (v.includes("progress")) return "progress";
  if (v.includes("resolved") || v.includes("closed")) return "done";
  return "open";
}

function priorityPill(p) {
  const cls = { High: "pill-high", Medium: "pill-medium", Low: "pill-low" }[p] || "pill-low";
  return '<span class="pill ' + cls + '">' + esc(p || "-") + "</span>";
}

function statusPill(s) {
  return '<span class="pill pill-' + statusGroup(s) + '">' + esc(s || "-") + "</span>";
}

// Counts for the stat cards
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
  const head =
    "<tr><th>ID</th><th>Title</th><th>Category</th><th>Priority</th><th>Status</th>" +
    (showPeople ? "<th>Created by</th>" : "") + "<th>Created</th></tr>";
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
  const groups = document.querySelectorAll(".nav-group");
  if (!groups.length) return;
  // Staff-only links (All Tickets) stay hidden for end users
  document.querySelectorAll(".staff-only").forEach((el) => { el.hidden = me.access_level < 2; });
  groups.forEach((group) => {
    const parent = group.querySelector(".nav-parent");
    parent.onclick = (e) => {
      if (window.innerWidth <= 900) return;          // small screens: just open the page
      e.preventDefault();
      parent.setAttribute("aria-expanded", group.classList.toggle("open"));
    };
  });
  // Fill "By Type" with the real categories (keeps the default three if the request fails)
  try {
    const cats = await api("/categories");
    if (cats.length) {
      $("type-list").innerHTML = cats.map((c) =>
        '<a href="TIcket_Q.html?view=type&type=' + encodeURIComponent(c.category_name) + '">' + esc(c.category_name) + "</a>").join("");
    }
  } catch (e) {}
  highlightNav();
}

// Marks the sub-link for the page we are on, and opens the right group
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
