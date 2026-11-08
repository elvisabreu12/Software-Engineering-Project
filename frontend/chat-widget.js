(function () {
  const API_URL = document.currentScript.dataset.api;
  const HISTORY_KEY = "hd-history";
 
  let history = [];
  try { history = JSON.parse(sessionStorage.getItem(HISTORY_KEY) || "[]"); } catch (e) {}
 
 
  const style = document.createElement("style");
  style.textContent = `
    #hd-btn { position:fixed; bottom:24px; right:24px; width:58px; height:58px; border-radius:50%;
      border:none; background:#1e1e2d; color:#fff; font-size:26px; cursor:pointer; z-index:9999;
      box-shadow:0 6px 20px rgba(30,30,45,.35); transition:transform .15s, background .15s; }
    #hd-btn:hover { transform:scale(1.07); background:#2a83e6; }
 
    #hd-panel { position:fixed; bottom:96px; right:24px; width:380px; max-width:calc(100vw - 32px);
      height:560px; max-height:calc(100vh - 120px); display:none; flex-direction:column;
      background:#fff; border-radius:16px; overflow:hidden; z-index:9999;
      box-shadow:0 18px 50px rgba(15,15,35,.28); font-family:Arial,Helvetica,sans-serif;
      animation:hd-pop .18s ease-out; }
    @keyframes hd-pop { from { opacity:0; transform:translateY(10px) scale(.98); } to { opacity:1; transform:none; } }
 
    #hd-head { background:#1e1e2d; color:#fff; padding:14px 16px; display:flex; align-items:center; gap:12px; }
    #hd-avatar { width:38px; height:38px; border-radius:50%; background:#2a2a40; display:flex;
      align-items:center; justify-content:center; font-size:20px; flex-shrink:0; }
    #hd-title { flex:1; min-width:0; }
    #hd-title b { display:block; font-size:15px; }
    #hd-title span { font-size:12px; color:#b5b5c3; display:flex; align-items:center; gap:6px; }
    #hd-title span::before { content:""; width:8px; height:8px; border-radius:50%; background:#3ecf8e; }
    .hd-icon { background:none; border:none; color:#b5b5c3; font-size:16px; cursor:pointer;
      padding:6px 8px; border-radius:6px; }
    .hd-icon:hover { background:#2a2a40; color:#fff; }
 
    #hd-msgs { flex:1; overflow-y:auto; padding:16px; background:#f8f9fa; display:flex;
      flex-direction:column; gap:12px; }
    .hd-row { display:flex; flex-direction:column; max-width:86%; }
    .hd-row.hd-user { align-self:flex-end; align-items:flex-end; }
    .hd-row.hd-bot { align-self:flex-start; align-items:flex-start; }
    .hd-m { padding:10px 14px; border-radius:14px; font-size:14px; line-height:1.5; white-space:pre-wrap;
      word-wrap:break-word; }
    .hd-user .hd-m { background:#1e1e2d; color:#fff; border-bottom-right-radius:4px; }
    .hd-bot .hd-m { background:#fff; color:#3f4254; border:1px solid #e6e8ee; border-bottom-left-radius:4px; }
    .hd-time { font-size:11px; color:#a0a3b1; margin-top:4px; padding:0 4px; }
 
    .hd-sources { display:flex; flex-wrap:wrap; gap:6px; margin-top:6px; }
    .hd-src { font-size:12px; font-weight:bold; text-decoration:none; color:#2a83e6; background:#e8f1fd;
      padding:3px 10px; border-radius:999px; }
    .hd-src:hover { background:#d4e6fb; }
 
    .hd-chips { display:flex; flex-wrap:wrap; gap:8px; }
    .hd-chip { background:#fff; border:1px solid #d9dce5; color:#3f4254; font-size:13px; padding:7px 12px;
      border-radius:999px; cursor:pointer; }
    .hd-chip:hover { border-color:#2a83e6; color:#2a83e6; }
 
    .hd-typing { display:flex; gap:4px; padding:4px 2px; }
    .hd-typing i { width:7px; height:7px; border-radius:50%; background:#b5b5c3; animation:hd-bounce 1.2s infinite; }
    .hd-typing i:nth-child(2) { animation-delay:.15s; }
    .hd-typing i:nth-child(3) { animation-delay:.3s; }
    @keyframes hd-bounce { 0%,60%,100% { transform:translateY(0); opacity:.5; } 30% { transform:translateY(-5px); opacity:1; } }
 
    #hd-form { display:flex; align-items:center; gap:8px; padding:12px; border-top:1px solid #eceef3; background:#fff; }
    #hd-input { flex:1; border:1px solid #d9dce5; border-radius:999px; padding:11px 16px; font-size:14px;
      outline:none; color:#333; }
    #hd-input:focus { border-color:#2a83e6; box-shadow:0 0 0 3px rgba(42,131,230,.15); }
    #hd-send { width:42px; height:42px; border-radius:50%; border:none; background:#1e1e2d; color:#fff;
      font-size:18px; cursor:pointer; flex-shrink:0; }
    #hd-send:hover { background:#2a83e6; }
    #hd-send:disabled { opacity:.5; cursor:wait; }
    #hd-foot { text-align:center; font-size:11px; color:#a0a3b1; padding:0 0 8px; background:#fff; }
  `;
  document.head.appendChild(style);
 
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
 
  const msgs = panel.querySelector("#hd-msgs");
  const form = panel.querySelector("#hd-form");
  const input = panel.querySelector("#hd-input");
  const sendBtn = panel.querySelector("#hd-send");
 
  // ---------- Helpers ----------
  function clock(ts) {
    const d = ts ? new Date(ts) : new Date();
    return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }
 
  function scrollDown() { msgs.scrollTop = msgs.scrollHeight; }
 
  function save() {
    try { sessionStorage.setItem(HISTORY_KEY, JSON.stringify(history)); } catch (e) {}
  }
 
  // Adds one chat bubble. Returns the bubble element so the caller can change its text later.
  function addMessage(role, text, opts) {
    opts = opts || {};
    const row = document.createElement("div");
    row.className = "hd-row " + (role === "user" ? "hd-user" : "hd-bot");
 
    const bubble = document.createElement("div");
    bubble.className = "hd-m";
    bubble.textContent = text;
    row.appendChild(bubble);
 
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
    const plain = history.map((m) => ({ role: m.role, content: m.content }));
 
    try {
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
      history.push({ role: "user", content: question, time: now });
      history.push({ role: "assistant", content: data.answer, sources: data.sources || [], time: now });
      save();
    } catch (err) {
      typing.remove();
      addMessage("assistant", "Sorry, something went wrong. Please try again in a moment.");
    } finally {
      sendBtn.disabled = false;
      input.focus();
    }
  }
 
  // ---------- Events ----------
  function toggle(open) {
    const show = open === undefined ? panel.style.display !== "flex" : open;
    panel.style.display = show ? "flex" : "none";
    if (show) { scrollDown(); input.focus(); }
  }
 
  btn.onclick = () => toggle();
  panel.querySelector("#hd-close").onclick = () => toggle(false);
  panel.querySelector("#hd-clear").onclick = () => { history = []; save(); render(); };
  form.onsubmit = (e) => { e.preventDefault(); ask(input.value); };
 
  render();
})();
