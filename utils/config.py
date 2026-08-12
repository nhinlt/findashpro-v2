# utils/config.py
"""
NGUỒN SỰ THẬT DUY NHẤT cho mọi tham số tài chính của ứng dụng.

Lý do tồn tại của file này: trước đây lãi suất phi rủi ro có HAI giá trị khác nhau
trong cùng một app (0.045 ở pages/4, 0.04 hardcode ở core/portfolio_opt.py).
Mọi module từ nay chỉ được đọc tham số từ đây.
"""
from __future__ import annotations

# ----------------------------------------------------------------------------
# THAM SỐ THỊ TRƯỜNG
# ----------------------------------------------------------------------------
RISK_FREE_RATE: float = 0.045      # Lãi suất phi rủi ro NĂM (TPCP VN kỳ hạn 10 năm, xấp xỉ)
TRADING_DAYS: int = 252            # Số phiên giao dịch/năm dùng để năm hóa
TRANSACTION_COST: float = 0.0015   # Phí + thuế + trượt giá, mỗi lượt (0.15%)

MARKET_INDEX: str = "VNINDEX"      # Danh mục thị trường cho CAPM
SIZE_INDEX: str = "VN30"           # Rổ vốn hóa lớn, dùng dựng nhân tố quy mô cho APT

# ----------------------------------------------------------------------------
# GIẢ ĐỊNH VI CẤU TRÚC THỊ TRƯỜNG VIỆT NAM
# Hai hằng số dưới đây tồn tại vì backtest cũ đã vi phạm cả hai.
# ----------------------------------------------------------------------------
ALLOW_SHORT: bool = False          # TTCK Việt Nam KHÔNG cho bán khống cổ phiếu
SETTLEMENT_LAG: int = 2            # Chu kỳ thanh toán T+2: mua ngày T, bán được từ T+2
EXECUTION_LAG: int = 1             # Tín hiệu tính hết phiên T, khớp lệnh phiên T+1

# ----------------------------------------------------------------------------
# QUY ƯỚC TÍNH TOÁN
# ----------------------------------------------------------------------------
RETURN_CONVENTION: str = "log"     # Toàn app dùng LOG return. Không trộn với simple return.
RANDOM_SEED: int = 42              # Mọi mô phỏng phải tái lập được

# ----------------------------------------------------------------------------
# HIỂN THỊ
# ----------------------------------------------------------------------------
# ⚠️ KIỂM CHỨNG TRƯỚC KHI NỘP: in một giá đóng cửa ra và đối chiếu bảng giá thật.
# Endpoint entrade trả giá theo nghìn đồng cho cổ phiếu (VCB ~ 61.5 nghĩa là 61.500đ).
PRICE_UNIT: str = "nghìn VND"
PRICE_SCALE: int = 1_000           # Nhân với hệ số này để ra VND

# BẢNG MÀU — nguồn duy nhất. Đổi ở đây là đổi toàn app (CSS đọc lại các giá trị
# này trong ui/styles.css, biểu đồ đọc trực tiếp).
PLOTLY_TEMPLATE: str = "plotly_white"  # MỘT template cho toàn app, nền trắng
ACCENT: str = "#1B4F8A"                # Xanh navy — màu nhấn chính, đọc rõ trên nền trắng
ACCENT_SOFT: str = "#E8EEF7"           # Nền nhạt cùng tông với ACCENT
ACCENT_UP: str = "#0E8A5F"             # Xanh lá đậm — phiên tăng
ACCENT_DOWN: str = "#C62828"           # Đỏ đậm — phiên giảm
MUTED: str = "#5B6B7C"                 # Xám xanh — chú thích, đường tham chiếu
GRID: str = "#E4E8EF"                  # Lưới biểu đồ

# Màu tô vùng (fan chart, vùng biên độ) suy ra từ ACCENT để không lệch tông
ACCENT_FILL_LIGHT: str = "rgba(27, 79, 138, 0.10)"
ACCENT_FILL_MID: str = "rgba(27, 79, 138, 0.22)"

# Font: sans-serif cho chữ đọc, mono chỉ dùng cho CON SỐ để so hàng thẳng cột
FONT_SANS: str = "Inter, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
FONT_MONO: str = "JetBrains Mono, SF Mono, Consolas, Courier New, monospace"

# ----------------------------------------------------------------------------
# DANH SÁCH CỔ PHIẾU (yêu cầu [1]: "chọn từ danh sách")
# ----------------------------------------------------------------------------
UNIVERSE: dict[str, list[str]] = {
    "Ngân hàng":          ["VCB", "TCB", "MBB", "ACB", "CTG", "BID", "VPB", "STB"],
    "Bất động sản":       ["VIC", "VHM", "VRE", "NVL", "KDH", "DXG", "PDR"],
    "Sản xuất & Tiêu dùng": ["HPG", "VNM", "MSN", "SAB", "DHG", "GVR", "HSG"],
    "Công nghệ & Bán lẻ": ["FPT", "MWG", "PNJ", "CMG", "DGW"],
    "Năng lượng":         ["GAS", "PLX", "POW", "PVD", "REE"],
    "Chỉ số":             ["VNINDEX", "VN30", "HNXINDEX"],
}
INDEX_SYMBOLS: set[str] = set(UNIVERSE["Chỉ số"])
ALL_TICKERS: list[str] = sorted({t for v in UNIVERSE.values() for t in v})

# Danh mục mẫu để trang Portfolio có sẵn thứ gì đó chạy được khi demo
DEFAULT_PORTFOLIO: dict[str, float] = {"FPT": 0.30, "VCB": 0.25, "HPG": 0.25, "VNM": 0.20}


def is_index(ticker: str) -> bool:
    """Cho biết mã là chỉ số hay cổ phiếu, để định tuyến endpoint API."""
    return ticker.upper() in INDEX_SYMBOLS


def daily_rf() -> float:
    """Lãi suất phi rủi ro quy về một phiên."""
    return RISK_FREE_RATE / TRADING_DAYS
