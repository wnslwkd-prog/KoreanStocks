"""
공유 피처 추출 로직
===================
trainer.py (학습) 과 prediction_model.py (추론) 양쪽에서 import해 사용.
BASE_FEATURE_COLS 20개만 계산 — 미사용 중간 피처 제거로 수집 속도 개선.
"""
import numpy as np
import pandas as pd
from koreanstocks.core.config import config


def build_features(
    df: pd.DataFrame,
    market_df: pd.DataFrame = None,
    macro_df: pd.DataFrame = None,
) -> pd.DataFrame:
    """지표(indicator) DataFrame → BASE_FEATURE_COLS 20개 추출.

    학습(trainer.py)과 추론(prediction_model.py)에서 동일 로직을 사용해
    train/serve 피처 불일치(feature skew)를 방지한다.

    Parameters
    ----------
    df         : indicators.calculate_all() 결과 (OHLCV + 기술적 지표 컬럼 포함)
    market_df  : 시장 지수 수익률 DataFrame (return_1m, return_3m 컬럼)
    macro_df   : 거시경제 DataFrame (vix_level, sp500_1m 컬럼)

    Returns
    -------
    DataFrame  : 유효 행만 포함 (NaN / ±inf 행 제거), 컬럼 = BASE_FEATURE_COLS 교집합
    """
    if df.empty:
        return df

    feat = pd.DataFrame(index=df.index)
    tdy  = config.TRADING_DAYS_PER_YEAR   # 252거래일

    # ── 변동성 / 추세 강도 ────────────────────────────────────
    feat['atr_ratio']   = (df['atr'] / df['close']).rolling(60).rank(pct=True)
    feat['adx']         = df['adx']

    bb_range            = (df['bb_high'] - df['bb_low']).replace(0, np.nan)
    feat['bb_position'] = (df['close'] - df['bb_low']) / bb_range
    feat['bb_width']    = (bb_range / df['bb_mid']).clip(0.01, 0.50)  # ±inf 방지

    # ── 중기 모멘텀 / 상대강도 ────────────────────────────────
    feat['high_52w_ratio'] = (
        df['close'] / df['close'].rolling(tdy, min_periods=60).max()
    )
    _return_1m = df['close'].pct_change(20)
    _return_3m = df['close'].pct_change(60)
    feat['mom_accel'] = _return_1m - _return_3m / 3.0

    if market_df is not None and not market_df.empty:
        aligned = market_df.reindex(feat.index).ffill()
        feat['rs_vs_mkt_3m'] = (_return_3m - aligned.get('return_3m', 0)).fillna(0)
    else:
        feat['rs_vs_mkt_3m'] = 0.0

    # ── 추세 / 가격 모멘텀 ────────────────────────────────────
    feat['macd_diff']         = df['macd_diff']
    feat['macd_slope_5d']     = df['macd_diff'].diff(5)
    feat['price_sma_5_ratio'] = df['close'] / df['sma_5']

    # ── 반전 / 패턴 신호 ─────────────────────────────────────
    if 'fisher' in df.columns:
        feat['fisher'] = df['fisher']
    if 'bullish_fractal' in df.columns:
        feat['bullish_fractal_5d'] = df['bullish_fractal'].rolling(5, min_periods=1).max()

    # ── 거래량 방향성 ─────────────────────────────────────────
    if 'mfi' in df.columns:
        feat['mfi'] = df['mfi']
    if 'vzo' in df.columns:
        feat['vzo'] = df['vzo']
    if 'obv' in df.columns:
        # OBV 10일 모멘텀: 거래량 추세 가속/감속 신호 (±1 클리핑)
        feat['obv_trend'] = df['obv'].pct_change(10).clip(-1.0, 1.0)
    feat['low_52w_ratio'] = (
        df['close'] / df['close'].rolling(tdy, min_periods=60).min()
    )

    # ── 극값 감지 / 반전 신호 ─────────────────────────────────
    if 'rsi' in df.columns:
        # RSI 정규화: 0~100 → 0~1, 과매도(0.3 이하)/과매수(0.7 이상) 극값 보존
        feat['rsi'] = df['rsi'] / 100.0
    if 'cci' in df.columns:
        # CCI rolling 20일 percentile: 레짐 독립적 0~1 정규화 (±100 이탈 극값 감지)
        feat['cci_pct'] = df['cci'].rolling(20, min_periods=1).rank(pct=True)

    # ── 거시경제 ──────────────────────────────────────────────
    if macro_df is not None and not macro_df.empty:
        aligned = macro_df.reindex(feat.index).ffill()
        # ffill 후에도 커버되지 않는 날짜(macro 시작 이전)는 중립값으로 채움
        feat['vix_level'] = aligned['vix_level'].fillna(20.0) if 'vix_level' in aligned.columns else 20.0
        feat['sp500_1m']  = aligned['sp500_1m'].fillna(0.0)   if 'sp500_1m'  in aligned.columns else 0.0
    else:
        feat['vix_level'] = 20.0
        feat['sp500_1m']  = 0.0

    return feat.replace([np.inf, -np.inf], np.nan).dropna()
