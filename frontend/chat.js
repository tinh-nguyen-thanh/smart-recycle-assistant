/* F3: khung chat nổi dùng chung cho các trang. Nạp sau auth.js (dùng AUTH_API, authHeaders). */
(function () {
  const style = document.createElement("style");
  style.textContent = `
    .sr-chat-btn{position:fixed;right:20px;bottom:20px;width:56px;height:56px;border:0;border-radius:50%;
      background:var(--deep,#0e3a30);color:#fff;font-size:22px;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,.25);z-index:1000}
    .sr-chat{position:fixed;right:20px;bottom:88px;width:min(360px,calc(100vw - 40px));height:min(480px,calc(100vh - 120px));
      display:none;flex-direction:column;background:#fff;border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,.25);z-index:1000;overflow:hidden}
    .sr-chat.open{display:flex}
    .sr-chat header{background:var(--deep,#0e3a30);color:#fff;padding:12px 16px;font-weight:600}
    .sr-chat-log{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:8px;background:var(--mint,#e6f1e8)}
    .sr-chat-msg{max-width:85%;padding:8px 12px;border-radius:10px;white-space:pre-line;line-height:1.4;font-size:14px}
    .sr-chat-msg.user{align-self:flex-end;background:var(--deep2,#14493d);color:#fff}
    .sr-chat-msg.bot{align-self:flex-start;background:#fff;color:var(--ink,#10231d)}
    .sr-chat form{display:flex;gap:8px;padding:10px;border-top:1px solid #ddd}
    .sr-chat input{flex:1;padding:8px 10px;border:1px solid #ccc;border-radius:8px;font:inherit}
    .sr-chat form button{border:0;border-radius:8px;padding:0 14px;background:var(--deep,#0e3a30);color:#fff;cursor:pointer}
  `;
  document.head.appendChild(style);

  const btn = document.createElement("button");
  btn.className = "sr-chat-btn";
  btn.setAttribute("aria-label", "Mở trợ lý phân loại rác");
  btn.innerHTML = '<i class="fa-solid fa-comments"></i>';

  const box = document.createElement("section");
  box.className = "sr-chat";
  box.innerHTML = `
    <header>Trợ lý phân loại rác</header>
    <div class="sr-chat-log" aria-live="polite"></div>
    <form>
      <input name="message" maxlength="500" autocomplete="off" aria-label="Câu hỏi" placeholder="Ví dụ: Pin hỏng bỏ ở đâu?">
      <button type="submit" aria-label="Gửi"><i class="fa-solid fa-paper-plane"></i></button>
    </form>`;
  document.body.append(btn, box);

  const log = box.querySelector(".sr-chat-log");
  const form = box.querySelector("form");
  const input = form.elements.message;

  function addMsg(role, text) {
    const div = document.createElement("div");
    div.className = "sr-chat-msg " + role;
    div.textContent = text; // textContent để không chạy HTML lạ trong câu trả lời
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  addMsg("bot", "Xin chào! Bạn muốn hỏi cách phân loại loại rác nào?");

  btn.addEventListener("click", () => {
    box.classList.toggle("open");
    if (box.classList.contains("open")) input.focus();
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    addMsg("user", message);
    input.value = "";
    input.disabled = true;
    const reply = addMsg("bot", "Đang trả lời...");
    try {
      const res = await fetch(AUTH_API + "/chat", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ message }),
      });
      if (res.status === 503) reply.textContent = "Chatbot tạm thời không hoạt động, bạn thử lại sau nhé.";
      else if (!res.ok) reply.textContent = "Có lỗi xảy ra, bạn thử lại nhé.";
      else reply.textContent = (await res.json()).answer;
    } catch (_) {
      reply.textContent = "Không kết nối được máy chủ.";
    }
    input.disabled = false;
    input.focus();
  });
})();