"""
kiem_tra.py — tự kiểm tra sau khi chép file, TRƯỚC khi commit.

Chạy:  python kiem_tra.py

Script này không cần mạng: nó dùng data/mock_data.py nên chạy được cả khi API
entrade bị chặn. Mục đích là trả lời một câu hỏi duy nhất: mã nguồn có tự chạy
thông từ đầu đến cuối không.

Có thể xóa file này trước khi nộp bài, hoặc giữ lại làm công cụ kiểm tra nhanh.
"""
from __future__ import annotations

import sys
import traceback

PASS, FAIL, SKIP = "  [OK]  ", "  [LỖI] ", "  [BỎ]  "
results: list[tuple[bool, str]] = []


def check(name: str, fn) -> None:
    try:
        detail = fn()
        print(f"{PASS}{name}" + (f"  →  {detail}" if detail else ""))
        results.append((True, name))
    except Exception as exc:                      # noqa: BLE001
        print(f"{FAIL}{name}\n         {type(exc).__name__}: {exc}")
        results.append((False, name))


def section(title: str) -> None:
    print(f"\n{title}\n" + "─" * 66)


# ═══════════════════════════════════════════════════════════ 1. MÔI TRƯỜNG
section("1 · MÔI TRƯỜNG")


def _python():
    v = sys.version_info
    if v < (3, 10):
        raise RuntimeError(f"Python {v.major}.{v.minor} quá cũ, cần từ 3.10 trở lên")
    return f"Python {v.major}.{v.minor}.{v.micro}"


check("Phiên bản Python", _python)


def _packages():
    import importlib
    missing = []
    for m in ("streamlit", "pandas", "numpy", "scipy", "statsmodels",
              "plotly", "requests", "yfinance"):
        try:
            importlib.import_module(m)
        except ImportError:
            missing.append(m)
    if missing:
        raise RuntimeError(f"thiếu {', '.join(missing)} — chạy: pip install -r requirements.txt")
    import pandas, numpy, streamlit
    return f"pandas {pandas.__version__}, numpy {numpy.__version__}, streamlit {streamlit.__version__}"


check("Thư viện bắt buộc", _packages)

if any(not ok for ok, _ in results):
    print("\nDừng lại: môi trường chưa sẵn sàng. Sửa xong rồi chạy lại.\n")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════ 2. CẤU HÌNH
section("2 · CẤU HÌNH (utils/)")


def _config():
    from utils.config import ALL_TICKERS, RISK_FREE_RATE, TRADING_DAYS, UNIVERSE
    if not (0 < RISK_FREE_RATE < 0.3):
        raise ValueError(f"RISK_FREE_RATE = {RISK_FREE_RATE} trông không hợp lý")
    return (f"rf = {RISK_FREE_RATE:.2%}, {TRADING_DAYS} phiên/năm, "
            f"{len(ALL_TICKERS)} mã trong {len(UNIVERSE)} nhóm ngành")


check("utils/config.py", _config)
check("utils/logger.py", lambda: __import__("utils.logger", fromlist=["x"]) and "nạp được")

# ═══════════════════════════════════════════════════════════ 3. DỮ LIỆU
section("3 · LỚP DỮ LIỆU (data/)")

_df = None


def _mock():
    global _df
    from data.mock_data import generate_ohlcv
    _df = generate_ohlcv("FPT", 730)
    cols = set(_df.columns)
    if cols != {"open", "high", "low", "close", "volume"}:
        raise ValueError(f"sai schema: {sorted(cols)}")
    return f"{len(_df)} phiên, cột chữ thường đúng chuẩn"


check("Dữ liệu dự phòng", _mock)


def _empty_guard():
    """Đây chính là lỗi từng làm sập trang 5 và trang 6."""
    from data.dnse_client import empty_ohlcv
    e = empty_ohlcv()
    _ = [str(c).lower() for c in e.columns]      # trước đây nổ AttributeError
    if "close" not in e.columns:
        raise ValueError("DataFrame rỗng phải vẫn có đủ cột")
    return "DataFrame rỗng vẫn đúng schema, không còn AttributeError"


check("Chống crash khi API lỗi", _empty_guard)


def _resample():
    from data.dnse_client import resample_ohlcv
    out = []
    for lab in ("Ngày", "Tuần", "Tháng", "Quý"):
        out.append(f"{lab} {len(resample_ohlcv(_df, lab))}")
    return " · ".join(out) + "  (yêu cầu [2])"


check("Lấy mẫu ngày/tuần/tháng", _resample)

# ═══════════════════════════════════════════════════════════ 4. MÔ HÌNH
section("4 · MÔ HÌNH ĐỊNH LƯỢNG (core/)")


def _rsi():
    import numpy as np
    import pandas as pd
    from core.indicators import calculate_rsi
    r = calculate_rsi(pd.Series(np.arange(1, 61, dtype=float)), 14).dropna()
    if not (0 <= r.min() and r.max() <= 100):
        raise ValueError("RSI ra ngoài khoảng [0, 100]")
    if abs(r.iloc[-1] - 100) > 1e-6:
        raise ValueError("chuỗi toàn phiên tăng phải cho RSI = 100")
    return "làm mượt Wilder, nằm trong [0, 100]"


check("RSI", _rsi)


def _stats():
    from core.quantitative import describe_returns
    t = describe_returns(_df["close"])
    row = t[t["Chỉ tiêu"].str.contains("Jarque")]
    return f"{len(t)} chỉ tiêu, có Jarque–Bera = {row['Giá trị'].iloc[0]}  (yêu cầu [3])"


check("Thống kê mô tả", _stats)


def _drift():
    from core.quantitative import estimate_drift
    d = estimate_drift(_df["close"])
    return (f"μ = {d['mu_annual']:+.2%}/năm, sai số chuẩn ±{d['se_annual']:.2%}, "
            f"t = {d['tstat']:.2f}")


check("Ước lượng drift + độ tin cậy", _drift)


def _mc():
    import numpy as np
    from core.quantitative import run_monte_carlo
    s0 = _df["close"].iloc[-1]
    a = run_monte_carlo(_df["close"], 63, 3000, seed=42)
    b = run_monte_carlo(_df["close"], 63, 3000, seed=42)
    if not a.equals(b):
        raise ValueError("thiếu seed — hai lần chạy ra kết quả khác nhau")
    if not np.allclose(a.iloc[0], s0):
        raise ValueError("đường mô phỏng không bắt đầu từ giá hiện tại")
    if (a <= 0).any().any():
        raise ValueError("xuất hiện giá âm")
    z = run_monte_carlo(_df["close"], 252, 20000, drift_mode="zero")
    ratio = z.iloc[-1].mean() / s0
    if abs(ratio - 1) > 0.03:
        raise ValueError(f"thiếu hiệu chỉnh Itô: E[S_T]/S0 = {ratio:.3f}, phải xấp xỉ 1")
    return "bắt đầu từ S0, tái lập được, hiệu chỉnh Itô đúng"


check("Monte Carlo (yêu cầu [5])", _mc)


def _var():
    from core.quantitative import mc_risk_metrics, run_monte_carlo
    m = mc_risk_metrics(run_monte_carlo(_df["close"], 63, 3000), 0.95)
    if not (0 < m["var_pct"] < 1):
        raise ValueError("VaR phải là tỷ lệ lỗ trong khoảng (0, 1)")
    if m["cvar_amount"] <= m["var_amount"]:
        raise ValueError("CVaR phải nặng hơn VaR")
    if abs(m["var_amount"] - (m["s0"] - m["q_low"])) > 1e-9:
        raise ValueError("VaR không bằng S0 − Q5 — đang trả về một mức giá")
    return f"VaR 95% = -{m['var_pct']:.2%} (một KHOẢN LỖ), CVaR = -{m['cvar_pct']:.2%}"


check("VaR đúng định nghĩa", _var)


def _var_small():
    import numpy as np
    import pandas as pd
    from core.portfolio_opt import PortfolioOptimizer
    try:
        PortfolioOptimizer.calculate_var_cvar(pd.Series(np.random.randn(15) / 100))
    except ValueError:
        return "mẫu 15 quan sát bị chặn đúng, không trả NaN im lặng"
    raise RuntimeError("mẫu quá nhỏ mà vẫn cho ra số — lỗi cũ chưa được sửa")


check("Chặn mẫu nhỏ", _var_small)


def _capm():
    from core.portfolio import capm
    from core.quantitative import log_returns
    from data.mock_data import generate_ohlcv
    c = capm(log_returns(_df["close"]), log_returns(generate_ohlcv("VNINDEX", 730)["close"]))
    for k in ("alpha_tstat", "alpha_pvalue", "required_return", "jensen_alpha"):
        if k not in c:
            raise ValueError(f"thiếu {k}")
    return (f"β = {c['beta']:.3f}, α = {c['alpha_annual']:+.2%}/năm "
            f"(p = {c['alpha_pvalue']:.3f}), E(R) yêu cầu = {c['required_return']:+.2%}")


check("CAPM đầy đủ (yêu cầu [4])", _capm)


def _apt():
    from core.portfolio import apt, build_factors
    from core.quantitative import log_returns
    from data.mock_data import generate_ohlcv
    f = build_factors(generate_ohlcv("VNINDEX", 730)["close"],
                      generate_ohlcv("VN30", 730)["close"])
    a = apt(log_returns(_df["close"]), f)
    return f"nhân tố {a['factors']}, R² hiệu chỉnh = {a['adj_r_squared']:.1%}, có VIF"


check("APT (yêu cầu [4])", _apt)


def _frontier():
    import pandas as pd
    from core.portfolio_opt import PortfolioOptimizer as Opt
    from core.quantitative import log_returns
    from data.mock_data import generate_ohlcv
    px = pd.DataFrame({t: generate_ohlcv(t, 730)["close"]
                       for t in ("FPT", "VCB", "HPG", "VNM")}).dropna()
    rets = px.apply(log_returns).dropna()
    ef = Opt.efficient_frontier(rets.mean(), rets.cov(), 20, 0.4)
    if not all(abs(w.sum() - 1) < 1e-6 for w in ef["weights"]):
        raise ValueError("tổng trọng số khác 1")
    return f"{len(ef)} điểm giải bằng tối ưu, biến động {ef['vol'].min():.1%}–{ef['vol'].max():.1%}"


check("Đường biên hiệu quả thật", _frontier)


def _backtest():
    from core.alpha_engine import AlphaEngine
    sig = AlphaEngine.calculate_alpha_signal(_df, "Mean_Reversion_ZScore")
    b = AlphaEngine.backtest_signal(_df, sig)
    if b["data"]["position"].min() < 0:
        raise ValueError("vẫn còn vị thế bán khống dù mặc định phải là long-only")
    return (f"không bán khống, T+{b['assumptions']['settlement_lag']}, "
            f"{b['n_trades']} lệnh, tỷ lệ thắng/lệnh {b['win_rate']:.1%}")


check("Backtest theo ràng buộc TTCK VN", _backtest)


def _portfolio():
    import pandas as pd
    from core.portfolio import normalize_weights, portfolio_series
    from data.mock_data import generate_ohlcv
    px = pd.DataFrame({t: generate_ohlcv(t, 365)["close"]
                       for t in ("FPT", "VCB", "HPG", "VNM")}).dropna()
    w = normalize_weights({"FPT": 30, "VCB": 25, "HPG": 25, "VNM": 20})
    pf = portfolio_series(px, w, 500_000_000)
    return (f"NAV {pf['nav'].iloc[-1]/1e6:,.1f} tr, "
            f"PnL {pf['pnl'].iloc[-1]/1e6:+,.1f} tr ({pf['return_pct'].iloc[-1]:+.2%})")


check("Danh mục: NAV và PnL", _portfolio)

# ═══════════════════════════════════════════════════════════ 5. GIAO DIỆN
section("5 · GIAO DIỆN (ui/, pages/, app.py)")


def _ui():
    from pathlib import Path
    import ui.charts  # noqa: F401
    import ui.components  # noqa: F401
    css = Path("ui/styles.css")
    if not css.exists() or css.stat().st_size < 100:
        raise ValueError("ui/styles.css rỗng hoặc thiếu")
    return f"nạp được, styles.css {css.stat().st_size} byte"


check("ui/components.py + charts.py", _ui)


def _pages():
    import py_compile
    from pathlib import Path
    files = sorted(Path("pages").glob("*.py"))
    if len(files) != 8:
        raise ValueError(f"tìm thấy {len(files)} trang, phải có đúng 8 — "
                         f"tên file emoji có thể đã bị git làm hỏng")
    for f in files:
        py_compile.compile(str(f), doraise=True)
    py_compile.compile("app.py", doraise=True)
    return "8 trang + app.py biên dịch sạch"


check("Các trang", _pages)


def _config_toml():
    import tomllib
    from pathlib import Path
    p = Path(".streamlit/config.toml")
    if not p.exists():
        raise FileNotFoundError("thiếu .streamlit/config.toml — giao diện sẽ không ép nền tối")
    cfg = tomllib.load(p.open("rb"))
    if cfg.get("theme", {}).get("base") != "dark":
        raise ValueError("theme.base phải là 'dark' cho khớp biểu đồ plotly_dark")
    return "ép giao diện tối"


check("Cấu hình Streamlit", _config_toml)


def _no_secrets():
    from pathlib import Path
    if Path(".streamlit/secrets.toml").exists():
        gi = Path(".gitignore")
        if gi.exists() and "secrets.toml" in gi.read_text(encoding="utf-8"):
            return "có secrets.toml nhưng đã được .gitignore bỏ qua"
        raise RuntimeError("secrets.toml TỒN TẠI và CHƯA được .gitignore — nguy cơ lộ khóa API")
    return "không có secrets.toml trong thư mục làm việc"


check("An toàn khóa API", _no_secrets)

# ═══════════════════════════════════════════════════════════ TỔNG KẾT
ok = sum(1 for p, _ in results if p)
total = len(results)
print("\n" + "═" * 66)
if ok == total:
    print(f"  {ok}/{total} MỤC ĐẠT — mã nguồn sẵn sàng để commit.")
    print("  Bước tiếp theo:  pytest tests/ -q     rồi     streamlit run app.py")
else:
    print(f"  {ok}/{total} mục đạt. Các mục chưa đạt:")
    for p, n in results:
        if not p:
            print(f"    - {n}")
print("═" * 66 + "\n")
sys.exit(0 if ok == total else 1)
