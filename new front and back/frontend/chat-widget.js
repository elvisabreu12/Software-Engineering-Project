// chat-widget.js is the floating chatbot button and window that shows up on the pages.
// It sends the question to ragbot.py (port 8001) and shows the answer. The whole file is inside (function () { ... })();
// so its variables don't mix with the ones from app.js.
(function () {
  // the chatbot address comes from data-api on the <script> tag in the HTML page
  const API_URL = document.currentScript.dataset.api;
  const HISTORY_KEY = "hd-history";
 
  // history = the conversation so far. It is kept in sessionStorage so the chat is still there after changing pages.
  let history = [];
  try { history = JSON.parse(sessionStorage.getItem(HISTORY_KEY) || "[]"); } catch (e) {}
 
 
  // The CSS for the chat window is written here in JS, so every page that adds this script gets the styling without needing another css file.
  const style = document.createElement("style");
  style.textContent = `
    #hd-btn { position:fixed; bottom:24px; right:24px; width:58px; height:58px; border-radius:50%;
      border:none; background:var(--accent-dark,#1e1e2d); color:#fff; font-size:26px; cursor:pointer; z-index:9999;
      box-shadow:0 6px 20px rgba(30,30,45,.35); transition:transform .15s, background .15s; }
    #hd-btn:hover { transform:scale(1.07); background:var(--accent,#2a83e6); }
 
    #hd-panel { position:fixed; bottom:96px; right:24px; width:380px; max-width:calc(100vw - 32px);
      height:560px; max-height:calc(100vh - 120px); display:none; flex-direction:column;
      background:#fff; border-radius:16px; overflow:hidden; z-index:9999;
      box-shadow:0 18px 50px rgba(15,15,35,.28); font-family:Arial,Helvetica,sans-serif;
      animation:hd-pop .18s ease-out; }
    @keyframes hd-pop { from { opacity:0; transform:translateY(10px) scale(.98); } to { opacity:1; transform:none; } }
 
    #hd-head { background:var(--accent-dark,#1e1e2d); color:#fff; padding:14px 16px; display:flex; align-items:center; gap:12px; }
    #hd-avatar { width:38px; height:38px; border-radius:50%; background:var(--accent,#2a2a40); display:flex;
      align-items:center; justify-content:center; font-size:20px; flex-shrink:0; }
    #hd-title { flex:1; min-width:0; }
    #hd-title b { display:block; font-size:15px; }
    #hd-title span { font-size:12px; color:#b5b5c3; display:flex; align-items:center; gap:6px; }
    #hd-title span::before { content:""; width:8px; height:8px; border-radius:50%; background:#3ecf8e; }
    .hd-icon { background:none; border:none; color:#b5b5c3; font-size:16px; cursor:pointer;
      padding:6px 8px; border-radius:6px; }
    .hd-icon:hover { background:var(--accent,#2a2a40); color:#fff; }
 
    #hd-msgs { flex:1; overflow-y:auto; padding:16px; background:#f8f9fa; display:flex;
      flex-direction:column; gap:12px; }
    .hd-row { display:flex; flex-direction:column; max-width:86%; }
    .hd-row.hd-user { align-self:flex-end; align-items:flex-end; }
    .hd-row.hd-bot { align-self:flex-start; align-items:flex-start; }
    .hd-m { padding:10px 14px; border-radius:14px; font-size:14px; line-height:1.5; white-space:pre-wrap;
      word-wrap:break-word; }
    .hd-user .hd-m { background:var(--accent-dark,#1e1e2d); color:#fff; border-bottom-right-radius:4px; }
    .hd-bot .hd-m { background:#fff; color:#3f4254; border:1px solid #e6e8ee; border-bottom-left-radius:4px; }
    .hd-time { font-size:11px; color:#a0a3b1; margin-top:4px; padding:0 4px; }
 
    .hd-sources { display:flex; flex-wrap:wrap; gap:6px; margin-top:6px; }
    .hd-src { font-size:12px; font-weight:bold; text-decoration:none; color:var(--accent,#2a83e6); background:var(--accent-soft,#e8f1fd);
      padding:3px 10px; border-radius:999px; }
    .hd-src:hover { background:var(--accent-soft,#d4e6fb); }
 
    .hd-chips { display:flex; flex-wrap:wrap; gap:8px; }
    .hd-chip { background:#fff; border:1px solid #d9dce5; color:#3f4254; font-size:13px; padding:7px 12px;
      border-radius:999px; cursor:pointer; }
    .hd-chip:hover { border-color:var(--accent,#2a83e6); color:var(--accent,#2a83e6); }
 
    .hd-typing { display:flex; gap:4px; padding:4px 2px; }
    .hd-typing i { width:7px; height:7px; border-radius:50%; background:#b5b5c3; animation:hd-bounce 1.2s infinite; }
    .hd-typing i:nth-child(2) { animation-delay:.15s; }
    .hd-typing i:nth-child(3) { animation-delay:.3s; }
    @keyframes hd-bounce { 0%,60%,100% { transform:translateY(0); opacity:.5; } 30% { transform:translateY(-5px); opacity:1; } }
 
    #hd-form { display:flex; align-items:center; gap:8px; padding:12px; border-top:1px solid #eceef3; background:#fff; }
    #hd-input { flex:1; border:1px solid #d9dce5; border-radius:999px; padding:11px 16px; font-size:14px;
      outline:none; color:#333; }
    #hd-input:focus { border-color:var(--accent,#2a83e6); box-shadow:0 0 0 3px rgba(42,131,230,.15); }
    #hd-send { width:42px; height:42px; border-radius:50%; border:none; background:var(--accent-dark,#1e1e2d); color:#fff;
      font-size:18px; cursor:pointer; flex-shrink:0; }
    #hd-send:hover { background:var(--accent,#2a83e6); }
    #hd-send:disabled { opacity:.5; cursor:wait; }
    #hd-foot { text-align:center; font-size:11px; color:#a0a3b1; padding:0 0 8px; background:#fff; }
  `;
  document.head.appendChild(style);
 
  // this makes the round button and the chat window and adds them to the page
  // ---------- Markup ----------
  const btn = document.createElement("button");
  btn.id = "hd-btn";
  btn.title = "IT helpdesk assistant";
  btn.textContent = "💭";
 
  const panel = document.createElement("div");
  panel.id = "hd-panel";
  panel.innerHTML = `
    <div id="hd-head">
      <div id="hd-avatar">💭</div>
      <div id="hd-title"><b>IT Helpdesk Assistant</b><span>Answers from solved tickets</span></div>
      <button class="hd-icon" id="hd-clear" title="Clear conversation" type="button">🗑</button>
      <button class="hd-icon" id="hd-close" title="Close" type="button">✕</button>
    </div>
    <div id="hd-msgs"></div>
    <form id="hd-form" autocomplete="off">
      <input id="hd-input" placeholder="Describe your problem..." maxlength="700" />
      <button id="hd-send" type="submit" title="Send">➤</button>
    </form>
    <div id="hd-foot">Based on past IT tickets. For new issues, open a ticket.</div>`;
  document.body.append(btn, panel);
 
  // grab the pieces of the chat window that we need to use later
  const msgs = panel.querySelector("#hd-msgs");
  const form = panel.querySelector("#hd-form");
  const input = panel.querySelector("#hd-input");
  const sendBtn = panel.querySelector("#hd-send");
 
  // ---------- Helpers ----------
  // turns a time into something like 3:45 PM
  function clock(ts) {
    const d = ts ? new Date(ts) : new Date();
    return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }
 
  // scroll to the newest message
  function scrollDown() { msgs.scrollTop = msgs.scrollHeight; }
 
  // save the history in sessionStorage
  function save() {
    try { sessionStorage.setItem(HISTORY_KEY, JSON.stringify(history)); } catch (e) {}
  }
 
  // Adds one chat bubble. Returns the bubble element so the caller can change its text later.
  function addMessage(role, text, opts) {
    opts = opts || {};
    const row = document.createElement("div");
    // the class decides which side the bubble is on (user on the right, bot on the left)
    row.className = "hd-row " + (role === "user" ? "hd-user" : "hd-bot");
 
    const bubble = document.createElement("div");
    bubble.className = "hd-m";
    // textContent (not innerHTML) so the text can't run as HTML. That keeps it safe.
    bubble.textContent = text;
    row.appendChild(bubble);
 
    // if the answer used some tickets, show them as links under the message
    if (opts.sources && opts.sources.length) {
      const wrap = document.createElement("div");
      wrap.className = "hd-sources";
      opts.sources.forEach((id) => {
        const a = document.createElement("a");
        a.className = "hd-src";
        a.href = "ticket.html?id=" + encodeURIComponent(id);
        a.textContent = "Ticket #" + id;
        wrap.appendChild(a);
      });
      row.appendChild(wrap);
    }
 
    if (!opts.noTime) {
      const t = document.createElement("div");
      t.className = "hd-time";
      t.textContent = clock(opts.time);
      row.appendChild(t);
    }
 
    msgs.appendChild(row);
    scrollDown();
    return { row, bubble };
  }
 
  // the three bouncing dots that show while we wait for the answer
  function addTyping() {
    const row = document.createElement("div");
    row.className = "hd-row hd-bot";
    row.innerHTML = '<div class="hd-m"><div class="hd-typing"><i></i><i></i><i></i></div></div>';
    msgs.appendChild(row);
    scrollDown();
    return row;
  }
 
  // Greeting + clickable example questions (only shown on an empty conversation)
  function showWelcome() {
    addMessage("assistant", "Hi! I'm the IT helpdesk assistant. Tell me what's wrong and I'll look for a similar problem our team already solved.", { noTime: true });
    const chips = document.createElement("div");
    chips.className = "hd-chips";
    ["My laptop won't turn on", "I can't connect to the VPN", "The printer is jammed"].forEach((q) => {
      const c = document.createElement("button");
      c.type = "button";
      c.className = "hd-chip";
      c.textContent = q;
      c.onclick = () => { chips.remove(); ask(q); };
      chips.appendChild(c);
    });
    msgs.appendChild(chips);
  }
 
  // draws the whole chat again from the history (used at the start and after clearing)
  function render() {
    msgs.innerHTML = "";
    if (!history.length) { showWelcome(); return; }
    addMessage("assistant", "Welcome back! Ask me another question.", { noTime: true });
    history.forEach((m) => addMessage(m.role, m.content, { sources: m.sources, time: m.time }));
  }
 
  // ---------- Sending a question ----------
  async function ask(question) {
    question = (question || "").trim();
    if (!question) return;
    input.value = "";
    sendBtn.disabled = true;
 
    const chips = msgs.querySelector(".hd-chips");
    if (chips) chips.remove();
 
    addMessage("user", question);
    const typing = addTyping();
 
    // The server only needs role + content, not our extra fields
    // the server only needs the role and the text, so the time and sources are left out
    const plain = history.map((m) => ({ role: m.role, content: m.content }));
 
    try {
      // send the question and the earlier messages to the chatbot server
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, history: plain }),
      });
      if (!res.ok) throw new Error("Server error");
      const data = await res.json();
      typing.remove();
      addMessage("assistant", data.answer, { sources: data.sources });
      const now = Date.now();
      // save both messages in the history so the next question has the context
      history.push({ role: "user", content: question, time: now });
      history.push({ role: "assistant", content: data.answer, sources: data.sources || [], time: now });
      save();
    // if the server is off or something fails, show a normal error message in the chat
    } catch (err) {
      typing.remove();
      addMessage("assistant", "Sorry, something went wrong. Please try again in a moment.");
    // this runs either way: turn the send button back on
    } finally {
      sendBtn.disabled = false;
      input.focus();
    }
  }
 
  // ---------- Events ----------
  // opens or closes the chat window. With no value it just flips it.
  function toggle(open) {
    const show = open === undefined ? panel.style.display !== "flex" : open;
    panel.style.display = show ? "flex" : "none";
    if (show) { scrollDown(); input.focus(); }
  }
 
  // the clear button removes the history and starts again
  btn.onclick = () => toggle();
  panel.querySelector("#hd-close").onclick = () => toggle(false);
  panel.querySelector("#hd-clear").onclick = () => { history = []; save(); render(); };
  form.onsubmit = (e) => { e.preventDefault(); ask(input.value); };
 
  render();
})();
