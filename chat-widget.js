(function(){
    const API_URL = document.currentScript.dataset.api;
    let history = [];
    try{ history = JSON.parse(sessionStorage.getItem("hd-history")||"[]");} catch (e){}

    const style = document.createElement("style");
  style.textContent = `
    #hd-btn { position:fixed; bottom:20px; right:20px; width:56px; height:56px; border-radius:50%;
      border:none; background:#1e1e2d; color:#fff; font-size:24px; cursor:pointer; z-index:9999; }
    #hd-panel { position:fixed; bottom:90px; right:20px; width:340px; height:460px; display:none;
      flex-direction:column; background:#fff; border:1px solid #ddd; border-radius:12px;
      box-shadow:0 8px 24px rgba(0,0,0,.2); z-index:9999; font-family:sans-serif; }
    #hd-msgs { flex:1; overflow-y:auto; padding:12px; }
    .hd-m { margin:6px 0; padding:8px 12px; border-radius:10px; max-width:85%; white-space:pre-wrap; font-size:14px; }
    .hd-user { background:#1e1e2d; color:#fff; margin-left:auto; }
    .hd-bot { background:#f1f5f9; color:#111; }
    #hd-form { display:flex; border-top:1px solid #ddd; }
    #hd-input { flex:1; border:none; padding:12px; font-size:14px; outline:none; }
    #hd-send { border:none; background:none; color:#1e1e2d; padding:0 14px; cursor:pointer; font-weight:bold; }
  `;
  document.head.appendChild(style);

  const btn = document.createElement("button");
  btn.id = "hd-btn";
  btn.textContent = "🐇";

  const panel = document.createElement("div");
  panel.id = "hd-panel";
  panel.innerHTML = `
    <div id="hd-msgs"></div>
    <form id="hd-form">
      <input id="hd-input" placeholder="Ask a question..." autocomplete="off" maxlength="1000" />
      <button id="hd-send" type="submit">Send</button>
    </form>`;
  document.body.append(btn, panel);

  const msgs = panel.querySelector("#hd-msgs");
  const form = panel.querySelector("#hd-form");
  const input = panel.querySelector("#hd-input");

  function addMessage(role, text) {
    const div = document.createElement("div");
    div.className = "hd-m " + (role === "user" ? "hd-user" : "hd-bot");
    div.textContent = text; 
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
    return div;
  }

  function save() {
    try { sessionStorage.setItem("hd-history", JSON.stringify(history)); } catch (e) {}
  }

  // Restore the conversation after a page reload / navigation
  addMessage("assistant", "Hi! Ask me an IT question.");
  history.forEach((m) => addMessage(m.role, m.content));

  btn.onclick = () => {
    panel.style.display = panel.style.display === "flex" ? "none" : "flex";
  };

  form.onsubmit = async (e) => {
    e.preventDefault();
    const question = input.value.trim();
    if (!question) return;
    input.value = "";
    addMessage("user", question);
    const thinking = addMessage("assistant", "...");

    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, history }),
      });
      if (!res.ok) throw new Error("Server error");
      const data = await res.json();
      thinking.textContent = data.answer;
      history.push({ role: "user", content: question });
      history.push({ role: "assistant", content: data.answer });
      save();
    } catch (err) {
      thinking.textContent = "Sorry, something went wrong. Please try again.";
    }
  };
})();
