/* F3: khung chat nổi dùng chung cho các trang. Nạp sau auth.js (dùng AUTH_API, authHeaders). */
(function () {
  const STORE = "sr_chat"; // sessionStorage: giữ tin nhắn khi chuyển trang, tự xóa khi đóng tab
  const GREETING = "Xin chào! Bạn muốn hỏi cách phân loại loại rác nào?";
  const SUGGESTIONS = [
    "Pin điện thoại hỏng bỏ ở đâu?",
    "Hộp pizza dính dầu có tái chế được không?",
    "Túi ni lông bỏ thùng nào?",
  ];

  const style = document.createElement("style");
  style.textContent = `
    .sr-chat-btn{position:fixed;right:20px;bottom:20px;width:56px;height:56px;border:0;border-radius:50%;
      background:var(--deep,#0e3a30);color:#fff;font-size:22px;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,.25);z-index:1000}
    .sr-chat{position:fixed;right:20px;bottom:88px;width:min(360px,calc(100vw - 40px));height:min(480px,calc(100vh - 120px));
      display:none;flex-direction:column;background:#fff;border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,.25);z-index:1000;overflow:hidden}
    .sr-chat.open{display:flex}
    .sr-chat header{display:flex;justify-content:space-between;align-items:center;
      background:var(--deep,#0e3a30);color:#fff;padding:12px 16px;font-weight:600}
    .sr-chat-close{background:none;border:0;color:#fff;font-size:22px;line-height:1;cursor:pointer}
    .sr-chat-log{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:8px;background:var(--mint,#e6f1e8)}
    .sr-chat-msg{max-width:85%;padding:8px 12px;border-radius:10px;white-space:pre-line;line-height:1.4;font-size:14px}
    .sr-chat-msg.user{align-self:flex-end;background:var(--deep2,#14493d);color:#fff}
    .sr-chat-msg.bot{align-self:flex-start;background:#fff;color:var(--ink,#10231d)}
    .sr-chat-chips{display:flex;flex-wrap:wrap;gap:6px}
    .sr-chat-chips button{border:1px solid var(--deep,#0e3a30);background:#fff;color:var(--deep,#0e3a30);
      border-radius:16px;padding:4px 10px;font-size:13px;cursor:pointer}
    .sr-chat-dots span{display:inline-block;width:7px;height:7px;margin:0 2px;border-radius:50%;
      background:var(--muted,#4d6258);animation:sr-chat-bounce 1s infinite}
    .sr-chat-dots span:nth-child(2){animation-delay:.15s}
    .sr-chat-dots span:nth-child(3){animation-delay:.3s}
    @keyframes sr-chat-bounce{0%,60%,100%{transform:translateY(0);opacity:.4}30%{transform:translateY(-5px);opacity:1}}
    @media (prefers-reduced-motion:reduce){.sr-chat-dots span{animation:none}}
    .sr-chat form{display:flex;gap:8px;padding:10px;border-top:1px solid #ddd}
    .sr-chat input{flex:1;padding:8px 10px;border:1px solid #ccc;border-radius:8px;font:inherit}
    .sr-chat form button{border:0;border-radius:8px;padding:0 14px;background:var(--deep,#0e3a30);color:#fff;cursor:pointer}
  `;
  document.head.appendChild(style);

  const btn = document.createElement("button");
  btn.className = "sr-chat-btn";
  btn.setAttribute("aria-label", "Mở trợ lý phân loại rác");
  btn.setAttribute("aria-expanded", "false");
  btn.innerHTML = '<i class="fa-solid fa-comments"></i>';

  const box = document.createElement("section");
  box.className = "sr-chat";
  box.innerHTML = `
    <header>Trợ lý phân loại rác
      <button type="button" class="sr-chat-close" aria-label="Đóng">&times;</button>
    </header>
    <div class="sr-chat-log" aria-live="polite"></div>
    <form>
      <input name="message" maxlength="500" autocomplete="off" aria-label="Câu hỏi" placeholder="Ví dụ: Pin hỏng bỏ ở đâu?">
      <button type="submit" aria-label="Gửi"><i class="fa-solid fa-paper-plane"></i></button>
    </form>`;
  document.body.append(btn, box);

  const log = box.querySelector(".sr-chat-log");
  const form = box.querySelector("form");
  const input = form.elements.message;

  function loadHistory() {
    try { return JSON.parse(sessionStorage.getItem(STORE)) || []; } catch (_) { return []; }
  }
  function saveHistory() {
    try { sessionStorage.setItem(STORE, JSON.stringify(history)); } catch (_) {}
  }
  const history = loadHistory();

  function addMsg(role, text) {
    const div = document.createElement("div");
    div.className = "sr-chat-msg " + role;
    div.textContent = text; // textContent để không chạy HTML lạ trong câu trả lời
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  function showSuggestions() {
    const chips = document.createElement("div");
    chips.className = "sr-chat-chips";
    for (const q of SUGGESTIONS) {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = q;
      b.addEventListener("click", () => send(q));
      chips.appendChild(b);
    }
    log.appendChild(chips);
  }

  addMsg("bot", GREETING);
  history.forEach((m) => addMsg(m.role, m.text));
  if (!history.length) showSuggestions();

  function setOpen(open) {
    box.classList.toggle("open", open);
    btn.setAttribute("aria-expanded", String(open));
    if (open) input.focus();
  }
  btn.addEventListener("click", () => setOpen(!box.classList.contains("open")));
  box.querySelector(".sr-chat-close").addEventListener("click", () => { setOpen(false); btn.focus(); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && box.classList.contains("open")) { setOpen(false); btn.focus(); }
  });

  async function send(message) {
    if (input.disabled) return; // đang chờ câu trả lời trước
    log.querySelector(".sr-chat-chips")?.remove();
    addMsg("user", message);
    history.push({ role: "user", text: message });
    saveHistory();
    input.disabled = true;

    const reply = addMsg("bot", "");
    reply.innerHTML = '<span class="sr-chat-dots" role="status" aria-label="Đang trả lời"><span></span><span></span><span></span></span>';
    let text = "";
    try {
      const res = await fetch(AUTH_API + "/chat", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ message }),
      });
      if (res.status === 503) text = "Chatbot tạm thời không hoạt động, bạn thử lại sau nhé.";
      else if (!res.ok) text = "Có lỗi xảy ra, bạn thử lại nhé.";
      else {
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          text += decoder.decode(value, { stream: true }); // stream: true để không cắt đôi chữ có dấu
          reply.textContent = text.trimStart();
          log.scrollTop = log.scrollHeight;
        }
      }
    } catch (_) {
      text = text || "Không kết nối được máy chủ.";
    }
    reply.textContent = text.trim() || "Có lỗi xảy ra, bạn thử lại nhé.";
    history.push({ role: "bot", text: reply.textContent });
    saveHistory();
    input.disabled = false;
    input.focus();
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message || input.disabled) return;
    input.value = "";
    send(message);
  });
})();