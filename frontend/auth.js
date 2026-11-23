/* F4: dùng chung cho các trang cần đăng nhập. login.html lưu token ở localStorage "sr_token". */
const AUTH_API = "http://127.0.0.1:8000";

function getToken() {
  try { return localStorage.getItem("sr_token"); } catch (_) { return null; }
}

/* Chưa đăng nhập thì không gửi header, vì "Bearer null" sẽ bị backend báo 401 */
function authHeaders(extra) {
  const t = getToken();
  return t ? { ...extra, Authorization: "Bearer " + t } : { ...extra };
}

/* Có token thì hỏi /auth/me: còn hạn thì hiện tên trên thanh menu, hết hạn thì xóa phiên */
(async function () {
  if (!getToken()) return;
  try {
    const r = await fetch(AUTH_API + "/auth/me", { headers: authHeaders() });
    if (r.status === 401) {
      localStorage.removeItem("sr_token");
      localStorage.removeItem("sr_user");
      return;
    }
    if (!r.ok) return;
    const u = await r.json();
    localStorage.setItem("sr_user", JSON.stringify(u));
    const btn = document.querySelector("a.btn-login");
    if (btn) {
      btn.href = "profile.html";
      btn.lastChild.textContent = " " + (u.name || u.email);
    }
  } catch (_) { /* backend chưa chạy: giữ nguyên giao diện */ }
})();