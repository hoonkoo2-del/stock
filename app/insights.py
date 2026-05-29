"""인사이트 엔진 — 사용자 본인의 매매 기록 회고 분석.

모두 과거 데이터 분석이며 투자 권유가 아니다.
현재 종가는 호출부에서 stock_key -> price 맵으로 넘긴다.
"""
from __future__ import annotations
from app.engine import Position


def _safe_div(a, b):
    return a / b if b else 0.0


def performance_stats(positions: list[Position]) -> dict:
    """C. 성과 통계 — 승률/평균손익/손익비/기대값."""
    sells = [s for p in positions for s in p.sells]
    if not sells:
        return {"trade_count": 0}
    wins = [s for s in sells if s.pnl_krw > 0]
    losses = [s for s in sells if s.pnl_krw < 0]
    win_rate = _safe_div(len(wins), len(sells))
    avg_win = _safe_div(sum(s.pnl_krw for s in wins), len(wins))
    avg_loss = _safe_div(sum(abs(s.pnl_krw) for s in losses), len(losses))
    profit_factor = _safe_div(avg_win, avg_loss) if avg_loss else 0.0
    expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss
    return {
        "trade_count": len(sells),
        "win_count": len(wins),
        "win_rate": round(win_rate * 100, 1),
        "avg_win_krw": round(avg_win),
        "avg_loss_krw": round(avg_loss),
        "profit_factor": round(profit_factor, 2),
        "expectancy_krw": round(expectancy),
        "total_realized_krw": round(sum(s.pnl_krw for s in sells)),
    }


def trading_habits(positions_with_price: list[tuple[Position, float]]) -> dict:
    """A. 매매 습관 진단 — 조기매도/처분효과/물타기성과.

    positions_with_price: [(Position, current_price), ...] (current_price=통화 기준)
    """
    sells = []
    buys = []
    for pos, cur in positions_with_price:
        for s in pos.sells:
            sells.append((s, cur))
        for b in pos.buys:
            buys.append((b, cur))

    result = {}

    # 너무 일찍 파는 경향: 매도 후(현재 종가 기준) 더 오른 비율
    if sells:
        higher = [1 for s, cur in sells if cur > s.price]
        changes = [(cur - s.price) / s.price * 100 for s, cur in sells if s.price]
        result["early_sell"] = {
            "ratio_pct": round(_safe_div(len(higher), len(sells)) * 100, 1),
            "avg_change_pct": round(_safe_div(sum(changes), len(changes)), 1),
            "count": len(sells),
        }

    # 처분효과: 이익 vs 손실 실현 거래의 평균 보유기간
    win_hold = [s.holding_days for p, _ in positions_with_price for s in p.sells if s.pnl_krw > 0]
    loss_hold = [s.holding_days for p, _ in positions_with_price for s in p.sells if s.pnl_krw < 0]
    if win_hold or loss_hold:
        result["disposition"] = {
            "win_avg_days": round(_safe_div(sum(win_hold), len(win_hold))),
            "loss_avg_days": round(_safe_div(sum(loss_hold), len(loss_hold))),
        }

    # 물타기 성과: 물타기 매수단가 대비 현재가가 올랐으면 성과
    ad = [(b, cur) for b, cur in buys if b.is_average_down]
    if ad:
        successes = [1 for b, cur in ad if cur > b.price]
        contrib = [(cur - b.price) / b.price * 100 for b, cur in ad if b.price]
        result["average_down"] = {
            "count": len(ad),
            "success_count": len(successes),
            "success_pct": round(_safe_div(len(successes), len(ad)) * 100, 1),
            "avg_contrib_pct": round(_safe_div(sum(contrib), len(contrib)), 1),
        }

    return result


def trend_alerts(positions_with_price: list[tuple[Position, float]],
                 recent_n: int = 5, threshold_pct: float = 60.0) -> list[dict]:
    """9. 매매 경향 알림 (노티) — 최근 N건 기준."""
    buys = sorted(
        [(b, cur) for pos, cur in positions_with_price for b in pos.buys],
        key=lambda x: x[0].dt, reverse=True)[:recent_n]
    sells = sorted(
        [(s, cur) for pos, cur in positions_with_price for s in pos.sells],
        key=lambda x: x[0].dt, reverse=True)[:recent_n]

    alerts = []
    if buys:
        # 매수 후 하락: 현재가 < 매수가
        down = sum(1 for b, cur in buys if cur < b.price)
        pct = down / len(buys) * 100
        if pct >= threshold_pct:
            alerts.append({
                "type": "buy_then_down",
                "message": f"최근 매수의 {pct:.0f}%가 이후 하락했어요. 매수 타이밍을 점검해보세요.",
            })
    if sells:
        # 매도 후 상승: 현재가 > 매도가
        up = sum(1 for s, cur in sells if cur > s.price)
        pct = up / len(sells) * 100
        if pct >= threshold_pct:
            alerts.append({
                "type": "sell_then_up",
                "message": f"최근 매도의 {pct:.0f}%가 이후 올랐어요. 너무 일찍 파는지 점검해보세요.",
            })
    return alerts
