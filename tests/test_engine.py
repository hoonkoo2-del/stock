"""첨부 이미지의 실제 매매 데이터로 계산 엔진을 검증한다."""
import sys, os
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.engine import Trade, compute_position, simulate_not_sold


def d(s):
    return datetime.strptime(s, "%Y.%m.%d")


def test_avgo():
    """브로드컴: 전량 매도 케이스. 평균단가/실현손익 검증."""
    trades = [
        Trade(d("2024.11.25"), "buy", 144, 30),
        Trade(d("2024.12.24"), "buy", 237, 2),
        Trade(d("2024.12.27"), "buy", 243.6, 6),
        Trade(d("2025.01.28"), "buy", 210, 4),
        Trade(d("2025.01.28"), "buy", 214, 1),
        Trade(d("2025.04.17"), "sell", 173.42, 5),
        Trade(d("2025.05.27"), "sell", 421, 38),
    ]
    pos = compute_position(trades)
    # 평균단가 = 7309.6 / 43 = 169.9907
    assert abs(pos.sells[0].avg_cost - 169.9907) < 0.001, pos.sells[0].avg_cost
    # 4/17 매도 5주 실현손익 (통화)
    assert abs(pos.sells[0].pnl_ccy - 17.1465) < 0.01, pos.sells[0].pnl_ccy
    # 5/27 매도 38주 실현손익 (통화)
    assert abs(pos.sells[1].pnl_ccy - 9538.35) < 0.1, pos.sells[1].pnl_ccy
    # 전량 매도 → 잔여 0
    assert abs(pos.qty) < 1e-9, pos.qty
    total = pos.realized_ccy
    assert abs(total - 9555.5) < 1.0, total
    print(f"[AVGO] 평균단가 {pos.sells[0].avg_cost:.2f} / 총 실현손익 ${total:,.2f} / 잔여 {pos.qty}")


def test_nvda():
    """엔비디아: 매수/매도 교차 + 부분 매도 + 잔여 보유 케이스."""
    trades = [
        Trade(d("2024.06.10"), "buy", 22.20, 200),
        Trade(d("2024.07.05"), "buy", 126.70, 1),
        Trade(d("2024.11.12"), "sell", 146.50, 1),
        Trade(d("2024.11.15"), "sell", 147.60, 3),
        Trade(d("2024.12.24"), "sell", 141.00, 5),
        Trade(d("2025.01.28"), "buy", 124.00, 5),
        Trade(d("2025.04.17"), "sell", 105.59, 5),
        Trade(d("2025.10.21"), "sell", 183.28, 40),
    ]
    pos = compute_position(trades)
    # 첫 매수 후 평균 ~22.20, 둘째 매수 후 ~22.72
    assert abs(pos.sells[0].avg_cost - 22.7199) < 0.01, pos.sells[0].avg_cost
    # 25.01.28 매수 후 평균 ~25.29
    assert abs(pos.sells[3].avg_cost - 25.29) < 0.05, pos.sells[3].avg_cost
    # 잔여 수량 = 206 매수 - 54 매도 = 152
    assert abs(pos.qty - 152) < 1e-9, pos.qty
    assert abs(pos.avg_cost - 25.29) < 0.05, pos.avg_cost
    print(f"[NVDA] 잔여 {pos.qty:.0f}주 @ ${pos.avg_cost:.2f} / 총 실현손익 ${pos.realized_ccy:,.2f}")

    # 시뮬레이션: 현재가 215.28 (이미지 헤더 값) 가정
    sim = simulate_not_sold(pos, current_price=215.28, current_fx=1.0)
    last = sim[-1]  # 25.10.21 40주 @183.28 매도분
    # 안 팔았으면: (215.28-25.29)*40 = 7599.6, 실제: (183.28-25.29)*40=6319.6 → 기회 +1280
    assert last["opportunity_krw"] > 1000, last
    print(f"[NVDA] 마지막 매도분 안 팔았다면 기회손익 ${last['opportunity_krw']:,.2f}")


if __name__ == "__main__":
    test_avgo()
    test_nvda()
    print("\n모든 엔진 테스트 통과 ✅")
