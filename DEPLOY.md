# Hướng dẫn public ứng dụng

Đích đến: **Streamlit Community Cloud** — miễn phí, nối thẳng GitHub, deploy trong vài phút.

---

## Bước 1 — Đẩy code lên GitHub

Nếu Windows, chạy dòng này **trước** để git không làm hỏng tên file có emoji trong `pages/`:

```bash
git config --global core.quotepath false
```

Sau đó:

```bash
cd findashpro
git add -A
git commit -m "fix: sửa mô hình định lượng, chống crash, bổ sung APT và lấy mẫu"
git push origin main
```

Kiểm tra trên GitHub thấy đủ **8 file trong `pages/`** với emoji hiển thị đúng. Nếu tên file
biến thành `1_\360\237\223\212_Summary.py` thì lệnh `core.quotepath` ở trên chưa chạy.

> **Nếu bạn từng commit khóa API vào repo:** khóa đó đã nằm trong lịch sử git và
> vẫn lộ dù bạn đã xóa file. Vào https://console.groq.com/keys **thu hồi khóa cũ và
> tạo khóa mới**. Xóa file ở commit sau không cứu được.

---

## Bước 2 — Deploy

1. Vào **https://share.streamlit.io**, đăng nhập bằng tài khoản GitHub.
2. Góc trên bên phải bấm **"Create app"** → chọn **"Yup, I have an app"**.
3. Điền:

   | Trường | Giá trị |
   |---|---|
   | Repository | `<tài-khoản-github>/findashpro` |
   | Branch | `main` |
   | Main file path | `app.py` |
   | App URL | ví dụ `findashpro-<tên-bạn>` → `findashpro-<tên-bạn>.streamlit.app` |

4. Mở **"Advanced settings"** — **đừng bỏ qua bước này**:

   - **Python version:** chọn **3.12** (bản đã dùng để phát triển và chạy test).
     Community Cloud mặc định lấy bản Python mới nhất mà Streamlit hỗ trợ, có thể khác
     máy bạn. **Python không đổi được sau khi deploy** — muốn đổi phải xóa app rồi
     deploy lại.
   - **Secrets:** dán vào ô này, không commit vào repo:

     ```toml
     GROQ_API_KEY = "gsk_khoa_that_cua_ban"
     ```

5. Bấm **Deploy**. Lần đầu mất 3–6 phút vì phải cài `scipy`, `statsmodels`, `yfinance`.
   Log build hiện ở cột phải, chỉ người có quyền ghi vào repo mới xem được.

Sau này mỗi lần `git push`, app tự cập nhật. Đổi `requirements.txt` thì mất thêm vài phút
để cài lại thư viện.

---

## Bước 3 — Kiểm tra ngay sau khi deploy (quan trọng nhất)

Đây là phần hướng dẫn chung không nói, nhưng quyết định app của bạn có dùng được không.

### 3.1. API giá có chạy từ máy chủ nước ngoài không?

Máy chủ Community Cloud đặt ở nước ngoài. Endpoint `services.entrade.com.vn` là API nội bộ
của một công ty chứng khoán Việt Nam — **có thể chặn hoặc timeout với IP ngoài Việt Nam**.

**Cách kiểm tra:** mở trang Summary. Nhìn nhãn ngay dưới tiêu đề:

- 🟢 **"dữ liệu trực tiếp"** → API chạy được từ cloud. Xong, không phải lo.
- 🟠 **"dữ liệu mô phỏng"** → API bị chặn. App vẫn chạy nhờ `data/mock_data.py`, nhưng
  **mọi con số đều là máy sinh ra**. Không được dùng bản cloud để bảo vệ.

**Nếu bị chặn**, ba lựa chọn theo thứ tự ưu tiên:

1. **Bảo vệ bằng bản chạy local** (`streamlit run app.py` trên laptop, mạng Việt Nam),
   giữ link cloud làm phương án dự phòng và để nộp bài. Đây là lựa chọn an toàn nhất.
2. **Nạp sẵn dữ liệu vào repo:** chạy local, lưu dữ liệu các mã cần demo thành file
   `.parquet` trong `data/`, cho `get_ohlcv()` đọc file khi API thất bại thay vì sinh
   dữ liệu giả. Số liệu thật, không phụ thuộc mạng.
3. **Đổi nguồn:** dùng `vnstock` (gọi qua nhiều nhà cung cấp trong nước) thay entrade.

### 3.2. Yahoo Finance có bị giới hạn tốc độ không?

Yahoo giới hạn theo IP, mà IP của Community Cloud là **dùng chung** với hàng nghìn app khác
nên hay bị chặn hơn máy cá nhân. Triệu chứng: trang Financials hiện "—" ở mọi ô.

App đã cache 900 giây nên tải một lần là dùng được cả buổi. Cứ mở trang Financials sớm
để "làm nóng" cache trước khi trình bày.

### 3.3. Giao diện có đúng tông tối không?

File `.streamlit/config.toml` đã ép `base = "dark"`. Mở app bằng một trình duyệt đang để
chế độ **sáng** để xác nhận — nếu không ép, người chấm mở máy chế độ sáng sẽ thấy biểu đồ
nền đen nằm trên trang nền trắng.

### 3.4. Bấm hết 8 trang một lượt

Mỗi trang chạy lần đầu mới lộ lỗi thiếu thư viện. Bấm hết 8 trang, đổi mã cổ phiếu vài lần,
đổi khung lấy mẫu, chạy Monte Carlo với 10.000 kịch bản.

---

## Ngày bảo vệ

| Việc | Thời điểm |
|---|---|
| Mở link app để đánh thức | **15 phút trước** — app ngủ sau 12 giờ không ai truy cập, lần đầu tải lại mất khoảng 30 giây |
| Bấm qua 8 trang để làm nóng cache | 10 phút trước |
| Mở sẵn bản local `streamlit run app.py` ở tab khác | dự phòng khi mạng phòng họp hỏng |
| Chụp màn hình 8 trang lưu vào slide | dự phòng cuối cùng — mất điện vẫn còn cái để trình bày |

---

## Giới hạn của gói miễn phí

| Mục | Giới hạn |
|---|---|
| Bộ nhớ | khoảng 1 GB — đủ cho app này (10.000 kịch bản × 252 phiên ≈ 20 MB) |
| Ngủ đông | sau 12 giờ không có truy cập; tự thức khi có người mở |
| App công khai | không giới hạn số lượng |
| App riêng tư | chỉ 1 |
| Tên miền riêng | không hỗ trợ |

Nếu vượt giới hạn, các lựa chọn khác: Hugging Face Spaces (miễn phí), Render hoặc Railway
(có gói miễn phí giới hạn), hoặc Docker trên VPS.

---

## Xử lý sự cố

| Triệu chứng | Nguyên nhân thường gặp |
|---|---|
| `ModuleNotFoundError` | thiếu gói trong `requirements.txt`, hoặc file không nằm ở gốc repo |
| Build treo ở "Installing dependencies" | `scipy`/`statsmodels` biên dịch lâu — chờ đủ 6 phút trước khi nghi ngờ |
| Chỉ thấy trang chủ, không có 8 trang | tên file trong `pages/` bị git làm hỏng (xem Bước 1) |
| Trang trắng, không báo lỗi | `showErrorDetails = false` đang giấu lỗi — xem log ở bảng điều khiển Cloud |
| Trang AI Assistant báo thiếu khóa | chưa dán Secrets, hoặc dán sai định dạng TOML (phải có dấu ngoặc kép) |
| Số liệu khác nhau giữa local và cloud | nhãn nguồn đang là "dữ liệu mô phỏng" trên cloud — xem mục 3.1 |

Xem log: vào https://share.streamlit.io → chọn app → **"Manage app"** ở góc dưới bên phải.
Nút **"Reboot app"** ở đó xử lý được phần lớn trục trặc tạm thời.
