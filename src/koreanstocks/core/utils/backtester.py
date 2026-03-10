import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from koreanstocks.core.config import config

class Backtester:
    """주식 투자 전략의 성과를 검증하는 백테스팅 엔진"""

    def __init__(self, initial_capital: float = 10000000.0):
        self.initial_capital = initial_capital
        self.fee = config.TRANSACTION_FEE
        self.tax = config.TAX_RATE

    def run(self, df: pd.DataFrame, signals: pd.Series, initial_capital: Optional[float] = None) -> Dict[str, Any]:
        """
        백테스팅 실행
        :param df: OHLCV 데이터프레임
        :param signals: 매수/매도 시그널
        :param initial_capital: 초기 투자 금액 (None일 경우 클래스 기본값 사용)
        :return: 성과 지표 딕셔너리
        """
        capital = initial_capital if initial_capital is not None else self.initial_capital

        if capital <= 0:
            return {"error": "initial_capital must be positive"}
        if df.empty or len(df) != len(signals):
            return {"error": "Invalid data or signals"}
        if 'close' not in df.columns:
            return {"error": "df must contain 'close' column"}

        results = df[['close']].copy()
        # values로 위치 기반 할당 — 인덱스 불일치 시 NaN 발생 방지
        results['signal'] = signals.values

        # 수익률 계산 (Daily Returns)
        results['pct_change'] = results['close'].pct_change()

        # 전략 수익률
        results['strategy_returns'] = results['signal'].shift(1) * results['pct_change']

        # 거래 비용 반영 — 첫 행은 diff()가 NaN이므로 초기 포지션 진입 비용 별도 처리
        trade = results['signal'].diff().abs()
        trade.iat[0] = abs(results['signal'].iat[0])
        results['trade'] = trade.fillna(0)
        cost_mask = results['trade'] > 0
        results.loc[cost_mask, 'strategy_returns'] -= (self.fee + self.tax)

        # 누적 수익률 및 자본금 계산
        strategy_returns = results['strategy_returns'].fillna(0)
        # 초기 포지션 진입 비용: strategy_returns[0]은 shift로 NaN → fillna 후 별도 차감
        # results['strategy_returns']에도 동기화하여 win_rate·Sharpe 계산과 일관성 유지
        if results['trade'].iat[0] > 0:
            strategy_returns.iat[0] -= (self.fee + self.tax)
            results['strategy_returns'].iat[0] = strategy_returns.iat[0]
        results['cum_returns'] = (1 + strategy_returns).cumprod()
        results['cum_capital'] = results['cum_returns'] * capital

        # 성과 지표
        last_cum = results['cum_returns'].iloc[-1]
        total_return = (last_cum - 1) * 100 if pd.notna(last_cum) else 0.0
        rolling_max = results['cum_returns'].cummax()
        drawdown = results['cum_returns'] / rolling_max - 1
        mdd_raw = drawdown.min()
        mdd = mdd_raw * 100 if pd.notna(mdd_raw) else 0.0

        nonzero_count = (results['strategy_returns'] != 0).sum()
        win_rate = (results['strategy_returns'] > 0).sum() / nonzero_count if nonzero_count > 0 else 0.0
        std = results['strategy_returns'].std()
        sharpe = (results['strategy_returns'].mean() / std) * np.sqrt(config.TRADING_DAYS_PER_YEAR) if std != 0 else 0.0

        return {
            "total_return_pct": round(total_return, 2),
            "mdd_pct": round(mdd, 2),
            "win_rate": round(win_rate * 100, 2),
            "sharpe_ratio": round(sharpe, 2),
            "final_capital": int(round(results['cum_capital'].iloc[-1])) if pd.notna(results['cum_capital'].iloc[-1]) else 0,
            "daily_results": results[['close', 'signal', 'cum_returns', 'cum_capital']]
        }

backtester = Backtester()
