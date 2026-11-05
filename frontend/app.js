// app.js - shared code for every page.
// This file is the ONLY place that knows how to talk to the backend.

// Where the FastAPI backend is running
const API = "http://127.0.0.1:8000";

// Shortcut for document.getElementById
const $ = (id) => document.getElementById(id);

// ---------- The login token (saved in the browser) ----------
const TOKEN_KEY = "wr_token";
function getToken() { try { return localStorage.getItem(TOKEN_KEY); } catch (e) { return null; } }
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
      "<td>" + esc(t.title) + "</td>" +
      "<td>" + esc(t.category || "-") + "</td>" +
      "<td>" + priorityPill(t.priority) + "</td>" +
      "<td>" + statusPill(t.status) + "</td>" +
      (showPeople ? "<td>" + esc(t.created_by || "-") + "</td>" : "") +
      '<td class="muted">' + esc(timeAgo(t.created)) + "</td>" +
    "</tr>").join("");
  return '<div class="table-wrap"><table class="tbl"><thead>' + head + "</thead><tbody>" + rows + "</tbody></table></div>";
}
