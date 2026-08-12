# FinDash Pro

Financial Dashboard cho thị trường chứng khoán Việt Nam. Xây dựng bằng Streamlit,
gồm 8 module bao phủ 5 yêu cầu của đề bài.

> Sản phẩm học thuật. Không phải khuyến nghị đầu tư.

---

## Chạy ứng dụng

```bash
git clone <repo-url> && cd findashpro
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Ứng dụng mở tại `http://localhost:8501`.

**Trang 8 (AI Assistant) cần khóa API — bảy trang còn lại chạy bình thường khi thiếu:**

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# rồi điền GROQ_API_KEY (lấy miễn phí tại https://console.groq.com/keys)
```

Chạy kiểm thử:

```bash
pytest tests/ -v
```

**Public thành app trực tuyến:** xem [`DEPLOY.md`](DEPLOY.md).

---

## Đối chiếu 5 yêu cầu của đề bài

| # | Yêu cầu | Thực hiện ở đâu |
|---|---|---|
| **[1]** | Summary — chọn cổ phiếu **từ danh sách** | `pages/1` — chọn theo nhóm ngành từ `utils/config.py::UNIVERSE`, kèm hồ sơ doanh nghiệp, giá, thanh khoản, biên độ 52 tuần |
| **[2]** | Chart + **lấy mẫu ngày/tuần/tháng** + Line/Candle | `pages/2` — Candle/Line/OHLC, lấy mẫu Ngày–Tuần–Tháng–Quý, SMA/EMA/Bollinger/RSI |
| **[3]** | Thống kê, tài chính, phân tích giá | `pages/3` — bảng thống kê mô tả (σ, skew, kurtosis, Jarque–Bera, Sharpe, MDD, VaR lịch sử), chỉ số định giá, KQKD/CĐKT/LCTT |
| **[4]** | Danh mục: **CAPM, APT** | `core/portfolio.py` — CAPM đầy đủ (t-stat, p-value, SML, lợi suất yêu cầu) và APT đa nhân tố (VIF, F-test). Áp dụng cho một mã ở `pages/4`, cho danh mục ở `pages/7`. Tối ưu Markowitz + đường biên hiệu quả ở `pages/6` |
| **[5]** | Monte Carlo Simulation | `core/quantitative.py` — GBM có hiệu chỉnh Itô và Bootstrap lịch sử, ba chế độ drift, VaR/CVaR đúng định nghĩa |

Hai module `pages/5` (Alpha Backtest) và `pages/8` (AI Assistant) nằm **ngoài** 5 yêu cầu.

---

## Kiến trúc

```
app.py                  Trang chủ + điểm vào
utils/config.py         ⭐ NGUỒN SỰ THẬT DUY NHẤT cho mọi tham số tài chính
utils/logger.py         Logger dùng chung
data/dnse_client.py     API giá (entrade) + get_ohlcv() an toàn + lấy mẫu
data/yfinance_client.py Dữ liệu cơ bản
data/mock_data.py       Dữ liệu dự phòng khi API sập
core/indicators.py      SMA, EMA, RSI (Wilder), Bollinger, MACD
core/quantitative.py    Monte Carlo + thống kê mô tả
core/portfolio.py       ⭐ CAPM, APT, NAV/PnL danh mục
core/portfolio_opt.py   Markowitz, đường biên hiệu quả, VaR/CVaR, Kupiec
core/alpha_engine.py    Tín hiệu Alpha + backtest
ui/components.py        ⭐ Widget dùng chung (chống lặp code)
ui/charts.py            Biểu đồ Plotly
ui/styles.css           ⭐ Toàn bộ CSS
pages/1..8              8 trang giao diện
tests/                  19 test cho SMA/EMA/RSI/Bollinger/MonteCarlo/VaR/CAPM
```

⭐ = file trước đây rỗng, nay đã được lấp đúng vai trò đã thiết kế.

**Nguyên tắc:** `pages/` chỉ làm giao diện; mọi phép tính tài chính nằm trong `core/`;
mọi truy cập mạng nằm trong `data/`; mọi tham số nằm trong `utils/config.py`.

---

## Giả định mô hình

Tất cả khai báo tại `utils/config.py`, hiển thị ở sidebar mọi trang.

| Tham số | Giá trị | Ghi chú |
|---|---|---|
| Lãi suất phi rủi ro | 4,5%/năm | **Một** giá trị duy nhất cho toàn app |
| Số phiên/năm | 252 | |
| Quy ước lợi suất | **log return** | Thống nhất mọi mô hình, không trộn với simple return |
| Bán khống | **Không** | TTCK Việt Nam không cho bán khống cổ phiếu |
| Thanh toán | **T+2** | Mua phiên T, bán được từ T+2 |
| Độ trễ khớp lệnh | T+1 | Tín hiệu chốt hết phiên T, khớp phiên sau — chống look-ahead bias |
| Phí giao dịch | 0,15%/lượt | Phí + thuế + trượt giá |
| Seed ngẫu nhiên | 42 | Mọi mô phỏng tái lập được |

---

## Giới hạn đã biết

Nêu ra vì che giấu giới hạn không làm chúng biến mất.

1. **Đơn vị giá cần kiểm chứng.** Endpoint entrade trả giá theo nghìn đồng cho cổ
   phiếu. Hãy in một giá đóng cửa và đối chiếu bảng giá thật trước khi tin số liệu.
2. **Giá điều chỉnh cổ tức/chia tách chưa được xác nhận.** Doanh nghiệp Việt Nam chia
   thưởng dày; nếu dùng giá thô thì mỗi lần chia tạo một cú sụt giả làm phồng biến động
   và méo beta. Cách kiểm tra: chọn một mã vừa chia tách, vẽ chuỗi giá, tìm cú rơi bất thường.
3. **Drift ước lượng từ lịch sử cực kỳ nhiễu.** Sai số chuẩn của μ bằng σ/√n; với 1–2
   năm dữ liệu nó thường lớn hơn chính giá trị ước lượng. Trang 4 hiển thị t-statistic và
   khoảng tin cậy của μ, và cho chọn drift trung tính rủi ro khi đo rủi ro.
4. **VaR ở trang 6 là in-sample.** Trọng số được tối ưu trên chính chuỗi dùng để đo VaR
   nên lạc quan có hệ thống. Kiểm định Kupiec được báo cáo kèm; muốn kết luận chắc chắn
   phải tách train/test.
5. **Backtest ở trang 5 là in-sample**, chưa tách train/test — không phải bằng chứng
   về hiệu quả ngoài mẫu.
6. **Yahoo Finance phủ dữ liệu cơ bản rất kém với cổ phiếu Việt Nam.** Ứng dụng hiển
   thị "—" cho trường thiếu và cảnh báo tỷ lệ thiếu, thay vì điền 0. Nguồn nội địa
   (vnstock, TCBS) sẽ đầy đủ hơn.
7. **API entrade là endpoint nội bộ, không có tài liệu công khai.** Khi không phản hồi,
   ứng dụng chuyển sang dữ liệu mô phỏng và **dán nhãn cảnh báo rõ ràng** trên màn hình.
8. **GBM giả định lợi suất log phân phối chuẩn.** Trang 3 kiểm định Jarque–Bera để
   người dùng tự thấy giả định có bị vi phạm không; trang 4 có phương án Bootstrap để đối chiếu.

---

## Nguồn dữ liệu

- **Giá:** DNSE / entrade `chart-api/v2` — cổ phiếu và chỉ số Việt Nam, cuối phiên
- **Cơ bản:** Yahoo Finance (`yfinance`) — hỗ trợ cả mã Việt Nam (`.VN`) và mã quốc tế
- **Trợ lý AI:** Groq
