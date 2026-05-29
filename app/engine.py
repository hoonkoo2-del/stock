"""핵심 계산 엔진 — 이동평균법 기반 평균단가/실현손익/보유/시뮬레이션.

모든 함수는 외부 네트워크에 의존하지 않는 순수 계산이다.
시세(현재 종가)는 호출부에서 인자로 넘긴다.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Trade:
    dt: datetime            # 거래 일시
    side: str               # 'buy' | 'sell'
    price: float            # 거래 통화 기준 단가
    qty: float              # 수량
    fx: float = 1.0         # 거래일 환율 (KRW/통화). 한국주식은 1.0
    tag: Optional[str] = None  # 사유 태그


@dataclass
class SellResult:
    dt: datetime
    price: float
    qty: float
    avg_cost: float         # 매도 시점 평균단가
    pnl_ccy: float          # 실현손익 (통화)
    pnl_krw: float          # 실현손익 (원)
    return_pct: float       # 수익률 %
    holding_days: float     # 가중평균 매수일~매도일 (근사)
    tag: Optional[str] = None


@dataclass
class BuyResult:
    dt: datetime
    price: float
    qty: float
    avg_before: float       # 직전 평균단가 (0이면 신규 진입)
    is_average_down: bool   # 물타기 여부 (price < avg_before 이고 기존 보유)
    tag: Optional[str] = None


@dataclass
class Position:
    qty: float = 0.0
    avg_cost: float = 0.0           # 잔여분 평균단가 (통화)
    cost_basis: float = 0.0         # 잔여 원가합 (통화)
    realized_ccy: float = 0.0       # 누적 실현손익 (통화)
    realized_krw: float = 0.0       # 누적 실현손익 (원)
    sells: list[SellResult] = field(default_factory=list)
    buys: list[BuyResult] = field(default_factory=list)


def compute_position(trades: list[Trade]) -> Position:
    """거래를 시간순으로 처리해 이동평균 평균단가와 실현손익을 계산한다."""
    ts = sorted(trades, key=lambda t: t.dt)
    pos = Position()
    # 가중평균 매수일 추적용 (epoch 초 가중)
    buy_qty_total = 0.0
    buy_time_weighted = 0.0  # sum(qty * epoch)

    for t in ts:
        if t.side == "buy":
            avg_before = pos.cost_basis / pos.qty if pos.qty else 0.0
            is_ad = bool(pos.qty > 0 and t.price < avg_before)
            pos.cost_basis += t.price * t.qty
            pos.qty += t.qty
            buy_qty_total += t.qty
            buy_time_weighted += t.qty * t.dt.timestamp()
            pos.buys.append(BuyResult(t.dt, t.price, t.qty, avg_before, is_ad, t.tag))
        else:  # sell
            if pos.qty <= 0:
                # 보유 없는 매도는 무시 (데이터 오류 방지)
                continue
            sell_qty = min(t.qty, pos.qty)
            avg = pos.cost_basis / pos.qty
            pnl_ccy = (t.price - avg) * sell_qty
            pnl_krw = pnl_ccy * t.fx
            ret = ((t.price - avg) / avg * 100.0) if avg else 0.0
            # 가중평균 매수일 → 보유기간 근사
            wavg_buy_epoch = (buy_time_weighted / buy_qty_total) if buy_qty_total else t.dt.timestamp()
            holding_days = max(0.0, (t.dt.timestamp() - wavg_buy_epoch) / 86400.0)

            pos.realized_ccy += pnl_ccy
            pos.realized_krw += pnl_krw
            pos.cost_basis -= avg * sell_qty
            pos.qty -= sell_qty
            pos.sells.append(SellResult(t.dt, t.price, sell_qty, avg, pnl_ccy,
                                        pnl_krw, ret, holding_days, t.tag))

    pos.avg_cost = pos.cost_basis / pos.qty if pos.qty else 0.0
    return pos


def simulate_not_sold(pos: Position, current_price: float,
                      current_fx: float = 1.0) -> list[dict]:
    """'안 팔았다면?' — 각 매도 건을 현재 종가로 평가해 실제 실현손익과 비교.

    매수원가는 매도 시점 평균단가(거래일 환율 반영된 실현손익 기준),
    현재 평가가치는 current_price/current_fx로 환산.
    """
    out = []
    for s in pos.sells:
        hypo_ccy = (current_price - s.avg_cost) * s.qty
        hypo_krw = hypo_ccy * current_fx
        out.append({
            "dt": s.dt,
            "sell_price": s.price,
            "qty": s.qty,
            "actual_pnl_krw": s.pnl_krw,
            "hypothetical_pnl_krw": hypo_krw,
            "opportunity_krw": hypo_krw - s.pnl_krw,  # 안 팔았으면 +/- 얼마
        })
    return out
