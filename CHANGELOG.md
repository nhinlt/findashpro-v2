# Nhật ký sửa lỗi

Đối chiếu với `Bao_Cao_Phan_Bien_V2_FinDashPro.md`. Cột "Ở đâu" ghi file đã sửa.

## Lỗi tài chính

| Lỗi | Trước | Sau | Ở đâu |
|---|---|---|---|
| **VaR không phải VaR** | `np.percentile(giá, 5)` gắn nhãn "VaR 95%" — đó là một *mức giá* | `VaR = S₀ − Q₅`, báo cáo cả số tiền lẫn % lỗ | `core/quantitative.py::mc_risk_metrics` |
| **Monte Carlo sai mô hình** | drift = 0, thiếu −½σ², `cumprod(1+r)`, `np.std` ddof=0, không seed, đường không bắt đầu từ S₀ | GBM có hiệu chỉnh Itô, ddof=1, seed cố định, vector hóa, hàng 0 = S₀, thêm Bootstrap | `core/quantitative.py::run_monte_carlo` |
| **Drift nhiễu không được nêu** | không đề cập | `estimate_drift()` báo t-stat + KTC 95%; cho chọn 3 chế độ drift | `core/quantitative.py`, `pages/4` |
| **Bán khống trên thị trường VN** | `np.clip(pos, -1, 1)` | mặc định long-only, bật/tắt được và ghi rõ giả định | `core/alpha_engine.py` |
| **Bỏ qua T+2** | đảo vị thế hằng ngày | `_apply_settlement()` giữ vị thế tối thiểu 2 phiên sau khi mua | `core/alpha_engine.py` |
| **CAPM thiếu kiểm định** | chỉ có Beta, Alpha, R² | thêm t-stat, p-value, KTC, alpha năm hóa | `core/portfolio.py::capm` |
| **CAPM không định giá** | dừng ở beta | thêm E(R) = Rf + β·MRP, Jensen's alpha, đường SML | `core/portfolio.py`, `pages/4` |
| **Hình CAPM lệch số** | hồi quy excess return, vẽ raw return | vẽ chính bộ dữ liệu đã hồi quy (`res["data"]`) | `pages/4` |
| **APT không tồn tại** | 0 dòng trong repo | hồi quy đa nhân tố MKT/SIZE/MOM, VIF, F-test, so R² với CAPM | `core/portfolio.py::apt` |
| **Efficient Frontier giả** | rắc trọng số ngẫu nhiên | giải min wᵀΣw tại từng mức lợi suất mục tiêu | `core/portfolio_opt.py::efficient_frontier` |
| **VaR/CVaR trả NaN im lặng** | `iloc[:0].mean()` khi mẫu nhỏ | chặn mẫu < 100 bằng `ValueError`; đuôi bao gồm điểm VaR; nội suy phân vị | `core/portfolio_opt.py` |
| **VaR in-sample không nêu** | không đề cập | thêm kiểm định Kupiec + ghi chú | `core/portfolio_opt.py`, `pages/6` |
| **rf hai giá trị** | 0.045 ở `pages/4`, 0.04 ở `portfolio_opt` | một hằng số duy nhất | `utils/config.py` |
| **Trộn log/simple return** | 4 quy ước trong 1 app | log return thống nhất | `utils/config.py`, `core/quantitative.py::log_returns` |
| **Sharpe không trừ rf** | `(mean/std)·√252` | Sharpe đúng + báo cáo riêng Information Ratio và Sortino | `core/alpha_engine.py` |
| **Win rate theo ngày** | `(daily_return > 0).mean()` | gộp phiên liên tiếp cùng chiều thành LỆNH | `core/alpha_engine.py` |
| **RSI không phải RSI** | `rolling(14).mean()` | làm mượt Wilder `ewm(alpha=1/14)` | `core/indicators.py` |
| **Thứ tự dropna sai** | `pct_change().dropna()` trên ma trận outer-join | `dropna()` trên **giá** trước | `pages/6`, `pages/7` |
| **fillna(0) trên BCTC** | quý thiếu doanh thu → doanh thu = 0 | giữ NaN, hiển thị "—", cảnh báo tỷ lệ thiếu | `data/yfinance_client.py` |
| **ffill khối lượng** | tạo thanh khoản giả | khối lượng khuyết → 0 | `data/dnse_client.py` |

## Lỗi crash

| Lỗi | Sửa | Ở đâu |
|---|---|---|
| `AttributeError` tại `.str.lower()` trên DataFrame rỗng (trang 5, 6) | `empty_ohlcv()` luôn trả đúng schema; `get_ohlcv()` guard trước | `data/dnse_client.py` |
| `KeyError: 'equity'` khi backtest trả DataFrame rỗng | guard ở tầng UI bằng `guard_model()` | `ui/components.py`, `pages/5` |
| `IndexError` tại `iloc[-2]` khi chỉ có 1 phiên | `guard_data(min_rows=2)` | `ui/components.py`, `pages/1` |
| Chia cho 0 khi khối lượng TB 20 phiên = 0 | kiểm tra trước khi chia | `pages/1` |
| OLS vỡ khi chọn chính VNINDEX | `rename("ri")` trước khi `concat` | `core/portfolio.py::_align` |
| `minimize()` không kiểm tra `res.success` | `RuntimeError` khi không hội tụ | `core/portfolio_opt.py::_solve` |
| API sập → app chết | `data/mock_data.py` + nhãn cảnh báo trên màn hình | `data/mock_data.py` |

## Kiến trúc & giao diện

| Lỗi | Sửa | Ở đâu |
|---|---|---|
| Không có `set_page_config` ở bất kỳ đâu | `setup_page()` với `layout="wide"` ở cả 9 file | `ui/components.py` |
| Không có README | README + `secrets.toml.example` | gốc repo |
| Ticker desync ở 3/8 trang | `ticker_selector()` dùng chung | `ui/components.py` |
| Không có danh sách cổ phiếu (yêu cầu [1]) | chọn theo nhóm ngành từ `UNIVERSE` | `utils/config.py` |
| `list(set(...))` xáo trộn thứ tự | list có thứ tự | `ui/components.py` |
| Không có lấy mẫu (yêu cầu [2]) | `resample_ohlcv()` Ngày/Tuần/Tháng/Quý | `data/dnse_client.py` |
| Không có thống kê mô tả (yêu cầu [3]) | `describe_returns()` 13 chỉ tiêu + Jarque–Bera | `core/quantitative.py` |
| Trang "Portfolio" không có danh mục | tỷ trọng, NAV, PnL, phân bổ, đóng góp, CAPM/APT cấp danh mục | `pages/7` |
| Chỉ có Income Statement | thêm Cân đối kế toán và Lưu chuyển tiền tệ | `data/yfinance_client.py` |
| `.VN` hardcode chặn mã quốc tế | tham số `suffix` + bộ chọn thị trường | `data/yfinance_client.py` |
| Ba tuyên bố sai trên trang chủ | gỡ "toàn cầu", "PnL thực tế", "phân tích tin tức" | `app.py` |
| Thiếu cache ở trang 3, 5, 6 | `@st.cache_data` toàn bộ đường truy cập dữ liệu | `data/`, `pages/` |
| `st.rerun()` thừa gây double-run | bỏ hoàn toàn | `ui/components.py` |
| CSS lặp ở 6 file, `styles.css` rỗng | một file CSS duy nhất | `ui/styles.css` |
| Template Plotly nhấp nháy sáng/tối | một template từ config | `ui/charts.py` |
| Đường 0% màu trắng trên nền trắng | dùng bảng màu từ config | `pages/7` |
| Lỗi chính tả "Quản Quản" | "Quản lý" | `app.py` |
| Comment "Gửi cho Gemini" nhưng dùng Groq | sửa comment, tách cờ lỗi khỏi lịch sử chat | `core/llm_client.py`, `pages/8` |
| AI không biết gì về mã đang chọn | `build_snapshot()` nạp giá + 13 chỉ tiêu thống kê vào ngữ cảnh | `pages/8` |
| `requirements.txt` 61 gói rác, 4 gói lõi không pin | 10 phụ thuộc trực tiếp, pin theo khoảng | `requirements.txt` |
| Test chỉ phủ SMA | 19 test: SMA/EMA/RSI/Bollinger + Monte Carlo/VaR/CAPM | `tests/` |
