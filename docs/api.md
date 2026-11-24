# Định dạng API – Smart Recycle Assistant

Bản nháp ngày 14/11/2026, do C soạn. Mục nào ghi **(đề xuất)** là chưa được cả nhóm chốt.
A và B điền phần của mình, sửa xong thì báo trong nhóm.

## Quy ước chung

- Địa chỉ khi chạy trên máy: `http://localhost:8000`
- Đường dẫn **không có tiền tố `/api`**, theo đúng file phân công (`/predict`, `/chat`...). **(đề xuất)**
  `frontend/home.html` hiện đang gọi `/api/predict`, cần sửa lại khi nối API.
- Dữ liệu gửi và nhận là JSON, trừ `/predict` gửi ảnh bằng `multipart/form-data`.
- Lỗi trả theo dạng mặc định của FastAPI: `{"detail": "nội dung lỗi"}`.
- Nhãn loại rác luôn dùng đúng tên trong `ai/models/labels.json`:
  `giay`, `nhua`, `kim_loai`, `thuy_tinh`, `huu_co`, `pin_nguy_hai`, `rac_khac`.
- Backend đọc thứ tự lớp từ `labels.json`, không ghi cứng trong code.
- Giao diện chạy bằng Live Server (cổng 5500) còn backend ở cổng 8000, nên B cần bật CORS
  cho `http://localhost:5500` và `http://127.0.0.1:5500`.

## Bảng tổng hợp

| Phương thức | Đường dẫn | Chức năng | Người làm | Cần đăng nhập |
|---|---|---|---|---|
| POST | `/predict` | F1 nhận diện ảnh, kèm F2 hướng dẫn | A | Không (có token thì gắn `user_id`) |
| GET | `/history` | F5 lịch sử quét | A | Có |
| GET | `/guide` | F2 toàn bộ bảng tri thức | C | Không |
| GET | `/guide/{label}` | F2 hướng dẫn cho một loại rác | C | Không |
| POST | `/feedback` | F7 lưu nhãn người dùng sửa | C | Không (chỉ sửa được lượt quét của mình) |
| GET | `/stats` | F6 thống kê | C | Có |
| POST | `/chat` | F3 chatbot RAG | B | Chưa chốt |
| POST | `/auth/register` | F4 đăng ký | B | Không |
| POST | `/auth/login` | F4 đăng nhập, trả JWT | B | Không |
| GET | `/auth/me` | F4 xem người đang đăng nhập | B | Có |
---

## POST /predict (A)

Gửi một ảnh, nhận về loại rác, độ tin cậy, nhóm rác và hướng dẫn xử lý.

**Gửi:** `multipart/form-data`, trường `file` là ảnh.

**Nhận:**

```json
{
  "id": 12,
  "label": "nhua",
  "confidence": 0.94,
  "group": {
    "id": "tai_che",
    "name": "Chất thải rắn có khả năng tái sử dụng, tái chế",
    "short": "Tái chế",
    "color": "#2a6fdb",
    "icon": "fa-recycle",
    "hint": "Sạch, khô, ép dẹp"
  },
  "guide": {
    "name": "Nhựa",
    "warning": null,
    "summary": "Đổ hết phần còn lại, tráng sơ, ép dẹp rồi gom riêng để tái chế.",
    "steps": ["Đổ hết nước hoặc thức ăn còn sót bên trong.", "..."],
    "dont": ["Không đốt nhựa vì tạo khói độc.", "..."],
    "examples": ["Chai nước", "..."],
    "reuse": "Cắt đáy chai làm chậu trồng rau mầm hoặc ống đựng bút."
  }
}
```

- `confidence` là số từ 0 đến 1. Giao diện coi dưới 0.6 là "AI chưa chắc chắn".
- `id` là mã bản ghi lịch sử, dùng cho `/feedback`. (A đã làm, backend trả đúng trường này)
- `group` và `guide` lấy bằng hàm có sẵn của C:

```python
from app.routers.guide import get_guide
group, guide = get_guide(label)
```

- `guide.warning` chỉ khác `null` với `pin_nguy_hai`; giao diện hiện khung cảnh báo đỏ khi có giá trị.

## GET /history (A)

Trả danh sách các lần quét, **mới nhất trước**.

**Tham số (query):**

- `limit`: số mục tối đa, mặc định 50, từ 1 đến 200.
- `offset`: bỏ qua bấy nhiêu mục đầu, mặc định 0 (dùng để phân trang).

Ví dụ: `GET /history?limit=20&offset=0`

**Nhận:**

```json
[
  {
    "id": 12,
    "label": "nhua",
    "confidence": 0.9971,
    "time": "2026-11-16T04:23:56+00:00",
    "image": "/uploads/844338b691094c4b82766ea90d7dadab.jpg"
  },
  {
    "id": 11,
    "label": "giay",
    "confidence": 0.88,
    "time": "2026-11-15T09:10:02+00:00",
    "image": "/uploads/a1b2c3d4....jpg",
    "corrected": true,
    "original": "nhua"
  }
]
```

- `label` là nhãn **cuối cùng**: nếu người dùng đã sửa nhãn thì là nhãn đã sửa.
- Chỉ khi đã sửa nhãn mới có thêm `corrected: true` và `original` (nhãn AI dự đoán).
- `time` theo ISO 8601, múi giờ UTC.
- `image` là đường dẫn tương đối. Ghép sau địa chỉ backend để hiện ảnh, ví dụ `http://localhost:8000/uploads/844338b6....jpg`. Có thể là `null` nếu bản ghi không có ảnh.
- Cần đăng nhập (`Authorization: Bearer <token>`). Chỉ trả lượt quét của người đang đăng nhập; thiếu hoặc sai token trả 401.
---
## GET /guide (C)

Trả toàn bộ nội dung `backend/app/data/f2_knowledge.json`, gồm `groups` và `labels`.
Giao diện (`frontend/knowledge.js`) dùng để dựng thùng rác, nút lọc, danh sách chọn lại nhãn.

## GET /guide/{label} (C)

Ví dụ `GET /guide/pin_nguy_hai`.

**Nhận:**

```json
{
  "label": "pin_nguy_hai",
  "group": { "id": "nguy_hai", "name": "Chất thải nguy hại", "short": "Nguy hại", "color": "#d23c27", "icon": "fa-triangle-exclamation", "hint": "Gom riêng, mang đến điểm thu" },
  "guide": { "name": "Pin và chất thải nguy hại", "warning": "Chất thải nguy hại! ...", "summary": "...", "steps": [], "dont": [], "examples": [], "reuse": "..." }
}
```

Nhãn không có trong bảng: trả mã 404.

## POST /feedback (C)

Người dùng bấm "Kết quả sai?" và chọn lại loại rác. Nhãn sửa được lưu để phân tích lỗi
và cải thiện mô hình.

**Gửi:**

```json
{ "id": 12, "label": "giay", "note": "Đây là hộp giấy chứ không phải chai nhựa" }
```

- `id`: mã bản ghi nhận từ `/predict`.
- `label`: nhãn đúng do người dùng chọn, phải thuộc `labels.json`.
- `note`: ghi chú của người dùng, không bắt buộc, tối đa 200 ký tự.

**Nhận:**

```json
{ "id": 12, "original": "nhua", "label": "giay", "corrected": true, "note": "Đây là hộp giấy chứ không phải chai nhựa" }
```

Nếu người dùng chọn lại đúng nhãn AI đã dự đoán thì `corrected` là `false`.

- Không bắt buộc đăng nhập. Lượt quét đã có chủ thì chỉ chủ (gửi kèm token) mới sửa được; người khác nhận 404 như khi id không tồn tại, để không lộ lượt quét của người khác.

## GET /stats (C)

Số liệu cho trang thống kê F6.

**Nhận:**

```json
{
  "total": 42,
  "by_group": { "tai_che": 25, "thuc_pham": 9, "nguy_hai": 3, "khac": 5 },
  "by_label": { "giay": 6, "nhua": 11, "kim_loai": 5, "thuy_tinh": 3, "huu_co": 9, "pin_nguy_hai": 3, "rac_khac": 5 },
  "corrected": 4,
  "by_day": [ { "date": "2026-11-14", "count": 7 } ],
  "corrections": [ { "from": "thuy_tinh", "to": "nhua", "count": 2 } ]
}
```

- Đếm theo nhãn cuối cùng (sau khi người dùng sửa, nếu có).
- `corrected` là số lần người dùng sửa nhãn.
- `by_day` gồm 7 ngày gần nhất, ngày không có lượt quét vẫn trả `count: 0`.
- `corrections` đếm các cặp "AI đoán `from`, người dùng sửa thành `to`", sắp giảm dần theo `count`.
  Trang `frontend/stats.html` dùng cho phần "AI hay nhầm ở đâu".
- Cần đăng nhập. Chỉ thống kê lượt quét của người đang đăng nhập; thiếu hoặc sai token trả 401.

---

## POST /chat (B)

B điền.

## POST /auth/register (B)

Tạo tài khoản mới. Đăng ký xong trả token luôn, người dùng không phải đăng nhập lại.

**Gửi:** `application/json`

```json
{
  "name": "Nguyễn Thanh Tính",
  "email": "tinh@test.com",
  "password": "12345678"
}
```

**Nhận (201):**

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": { "id": 1, "name": "Nguyễn Thanh Tính", "email": "tinh@test.com" }
}
```

- `name`: 1 đến 100 ký tự, được có dấu tiếng Việt.
- `email`: tối đa 100 ký tự, được đổi về chữ thường trước khi lưu, nên `Tinh@Test.com` và `tinh@test.com` là cùng một tài khoản.
- `password`: 8 đến 128 ký tự. Server chỉ lưu bản băm (PBKDF2-SHA256, salt riêng cho từng người), không lưu mật khẩu gốc.

## POST /auth/login (B)

**Gửi:** `application/json`

```json
{ "email": "tinh@test.com", "password": "12345678" }
```

**Nhận (200):** giống `/auth/register`.

- Sai email hay sai mật khẩu đều trả cùng một lỗi 401, để người khác không dò được email nào đã đăng ký.

## GET /auth/me (B)

Trả thông tin người đang đăng nhập. Cần gửi token.

**Nhận (200):**

```json
{ "id": 1, "name": "Nguyễn Thanh Tính", "email": "tinh@test.com" }
```

## Đăng nhập và token (B)

**Gửi token:** các API cần đăng nhập đọc header

```
Authorization: Bearer <token>
```

- Token là JWT (HS256), hết hạn sau 24 giờ. Hết hạn thì đăng nhập lại.
- Giao diện lưu token ở `localStorage` với khóa `sr_token`, thông tin người dùng ở khóa `sr_user`.
- Backend: muốn một API bắt buộc đăng nhập thì thêm tham số `user: User = Depends(get_current_user)` (import từ `app.security`).

**Mã lỗi:**

| Mã | Khi nào |
|---|---|
| 401 | Sai email hoặc mật khẩu; thiếu token, token hỏng hoặc hết hạn |
| 403 | Tài khoản bị khóa (`status` khác `active`) |
| 409 | Email đã được đăng ký |
| 422 | Dữ liệu gửi lên sai định dạng: thiếu trường, email sai, mật khẩu ngắn hơn 8 ký tự |

Lỗi trả dạng `{"detail": "thông báo"}`; `login.html` hiện thẳng nội dung `detail` cho người dùng.

**Chưa hỗ trợ:** đăng nhập bằng Google, Facebook, Zalo. Các nút này trên `login.html` đang chạy chế độ demo.

---

## Các việc đã chốt

1. Không dùng tiền tố `/api`.
2. `/predict` trả `id` bản ghi; không bắt buộc đăng nhập, có token thì lưu `user_id`.
3. Người chưa đăng nhập quét ảnh: vẫn lưu trên server với `user_id` rỗng; trang Lịch sử và Thống kê dùng dữ liệu trên trình duyệt.
4. `/stats` tính theo từng người dùng.