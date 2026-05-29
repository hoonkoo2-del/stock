"""기술적 지표 계산 및 종합 신호. 참고용 보조지표 (투자 권유 아님).

입력은 종가 시계열(pandas Series). 외부 네트워크 의존 없음.
"""
from __future__ import annotations


def _sma(series, n):
    return series.rolling(n).mean()


def _rsi(series, n=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(n).mean()
    loss = (-delta.clip(upper=0)).rolling(n).mean()
    rs = gain / loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def _macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    sig = macd.ewm(span=signal, adjust=False).mean()
    return macd, sig


def _bollinger(series, n=20, k=2):
    mid = series.rolling(n).mean()
    std = series.rolling(n).std()
    return mid + k * std, mid, mid - k * std


def analyze(close) -> dict:
    """종가 시리즈로 지표·종합 신호 산출. close: pandas Series (오름차순 날짜)."""
    if close is None or len(close) < 30:
        return {"ok": False, "reason": "데이터 부족 (최소 30 거래일 필요)"}

    last = float(close.iloc[-1])
    ma20 = _sma(close, 20)
    ma60 = _sma(close, 60)
    ma120 = _sma(close, 120) if len(close) >= 120 else None
    rsi = _rsi(close, 14)
    macd, sig = _macd(close)
    bb_up, bb_mid, bb_low = _bollinger(close, 20, 2)

    rsi_v = float(rsi.iloc[-1])
    macd_v = float(macd.iloc[-1])
    sig_v = float(sig.iloc[-1])
    ma20_v = float(ma20.iloc[-1])
    ma60_v = float(ma60.iloc[-1])

    signals = []
    score = 0  # +매수쪽 / -매도쪽

    # 추세 (단기 vs 중기 이평)
    if ma20_v > ma60_v:
        trend = "상승"
        score += 1
    elif ma20_v < ma60_v:
        trend = "하락"
        score -= 1
    else:
        trend = "횡보"

    # 골든/데드크로스 (직전 대비 교차)
    prev_diff = float(ma20.iloc[-2] - ma60.iloc[-2])
    cur_diff = ma20_v - ma60_v
    if prev_diff <= 0 < cur_diff:
        signals.append("골든크로스 발생 (20일선이 60일선 상향 돌파)")
        score += 1
    elif prev_diff >= 0 > cur_diff:
        signals.append("데드크로스 발생 (20일선이 60일선 하향 돌파)")
        score -= 1

    # RSI
    if rsi_v >= 70:
        signals.append(f"RSI {rsi_v:.0f} — 과매수 구간")
        score -= 1
    elif rsi_v <= 30:
        signals.append(f"RSI {rsi_v:.0f} — 과매도 구간")
        score += 1
    else:
        signals.append(f"RSI {rsi_v:.0f} — 중립")

    # MACD
    if macd_v > sig_v:
        signals.append("MACD 시그널 상향 (상승 모멘텀)")
        score += 1
    else:
        signals.append("MACD 시그널 하향 (하락 모멘텀)")
        score -= 1

    # 볼린저밴드
    bb_u, bb_l = float(bb_up.iloc[-1]), float(bb_low.iloc[-1])
    if last >= bb_u:
        signals.append("볼린저 상단 이탈 — 단기 과열 가능")
        score -= 1
    elif last <= bb_l:
        signals.append("볼린저 하단 이탈 — 단기 낙폭 과대 가능")
        score += 1

    if score >= 2:
        overall = "매수 우위 신호"
    elif score <= -2:
        overall = "매도 우위 신호"
    else:
        overall = "중립 / 관망"

    return {
        "ok": True,
        "price": round(last, 2),
        "trend": trend,
        "rsi": round(rsi_v, 1),
        "ma20": round(ma20_v, 2),
        "ma60": round(ma60_v, 2),
        "ma120": round(float(ma120.iloc[-1]), 2) if ma120 is not None else None,
        "overall": overall,
        "score": score,
        "signals": signals,
        "disclaimer": "본 신호는 투자 권유가 아닌 참고용 보조지표입니다. 최종 판단과 책임은 본인에게 있습니다.",
    }
