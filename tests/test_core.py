"""
핵심 모듈 단위 테스트
=====================
features.py · constants.py · indicators.py 의 핵심 함수를 검증.

실행:
    pytest tests/test_core.py -v
"""
import numpy as np
import pandas as pd
import pytest


# ─────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────

def _make_ohlcv(n: int = 120, base_price: float = 10_000) -> pd.DataFrame:
    """단조 상승하는 가상 OHLCV DataFrame 생성 (지표 계산에 충분한 행 수 확보)."""
    rng = pd.date_range("2024-01-01", periods=n, freq="B")
    prices = np.linspace(base_price, base_price * 1.3, n)
    return pd.DataFrame(
        {
            "open":   prices * 0.99,
            "high":   prices * 1.01,
            "low":    prices * 0.98,
            "close":  prices,
            "volume": np.full(n, 1_000_000),
        },
        index=rng,
    )


# ─────────────────────────────────────────────────────────────────
# constants.py — calc_composite_score 3-케이스
# ─────────────────────────────────────────────────────────────────

class TestCalcCompositeScore:
    from koreanstocks.core.constants import calc_composite_score

    def test_no_ml_model(self):
        """ML 모델 없음: tech 0.65 + sentiment_norm 0.35"""
        from koreanstocks.core.constants import calc_composite_score
        score = calc_composite_score(
            tech_score=60.0,
            ml_score=80.0,
            sentiment_score=0.0,       # norm=50
            ml_model_count=0,
        )
        expected = 0.65 * 60.0 + 0.35 * 50.0
        assert abs(score - expected) < 1e-6

    def test_with_ml_no_macro(self):
        """ML 있음, 거시감성 없음: tech 0.40 + ml 0.35 + stock_sent 0.25"""
        from koreanstocks.core.constants import calc_composite_score
        score = calc_composite_score(
            tech_score=70.0,
            ml_score=60.0,
            sentiment_score=20.0,      # norm=60
            ml_model_count=3,
        )
        expected = 0.40 * 70.0 + 0.35 * 60.0 + 0.25 * 60.0
        assert abs(score - expected) < 1e-6

    def test_with_ml_and_macro(self):
        """ML + 거시감성: tech 0.35 + ml 0.35 + stock_sent 0.20 + macro_sent 0.10"""
        from koreanstocks.core.constants import calc_composite_score
        score = calc_composite_score(
            tech_score=80.0,
            ml_score=70.0,
            sentiment_score=0.0,       # norm=50
            ml_model_count=5,
            macro_sentiment_score=50.0,  # norm=75
        )
        expected = 0.35 * 80.0 + 0.35 * 70.0 + 0.20 * 50.0 + 0.10 * 75.0
        assert abs(score - expected) < 1e-6

    def test_sentiment_clamp_lower(self):
        """sentiment_score=-100 → norm=0 (하한 클램프)."""
        from koreanstocks.core.constants import calc_composite_score
        score = calc_composite_score(
            tech_score=0.0,
            ml_score=0.0,
            sentiment_score=-100.0,
            ml_model_count=0,
        )
        # tech*0.65 + 0.0*0.35 = 0
        assert score == pytest.approx(0.0)

    def test_sentiment_clamp_upper(self):
        """sentiment_score=+100 → norm=100 (상한 클램프)."""
        from koreanstocks.core.constants import calc_composite_score
        score = calc_composite_score(
            tech_score=100.0,
            ml_score=100.0,
            sentiment_score=100.0,
            ml_model_count=0,
        )
        assert score == pytest.approx(100.0)

    def test_weights_sum_to_one(self):
        """가중치 합 = 1 (각 케이스 검증)."""
        from koreanstocks.core.constants import _W_TECH_ML, _W_TECH_ML_NM, _W_TECH_NOML
        assert sum(_W_TECH_ML)    == pytest.approx(1.0)
        assert sum(_W_TECH_ML_NM) == pytest.approx(1.0)
        assert sum(_W_TECH_NOML)  == pytest.approx(1.0)


# ─────────────────────────────────────────────────────────────────
# features.py — build_features() shape / columns
# ─────────────────────────────────────────────────────────────────

class TestBuildFeatures:
    def test_output_has_all_base_columns(self):
        """build_features() 반환 DataFrame 에 BASE_FEATURE_COLS 28개가 모두 포함되어야 함."""
        from koreanstocks.core.engine.features import build_features, BASE_FEATURE_COLS
        from koreanstocks.core.engine.indicators import indicators

        df = _make_ohlcv(150)
        df_with_indicators = indicators.calculate_all(df)
        result = build_features(df_with_indicators)

        missing = [c for c in BASE_FEATURE_COLS if c not in result.columns]
        assert not missing, f"누락된 피처: {missing}"

    def test_base_feature_count(self):
        """BASE_FEATURE_COLS 는 정확히 28개여야 함."""
        from koreanstocks.core.engine.features import BASE_FEATURE_COLS
        assert len(BASE_FEATURE_COLS) == 28

    def test_no_duplicate_feature_names(self):
        """피처 이름 중복 없음."""
        from koreanstocks.core.engine.features import BASE_FEATURE_COLS
        assert len(BASE_FEATURE_COLS) == len(set(BASE_FEATURE_COLS))

    def test_output_is_not_empty(self):
        """충분한 데이터로 빌드하면 빈 DataFrame 이 아니어야 함."""
        from koreanstocks.core.engine.features import build_features
        from koreanstocks.core.engine.indicators import indicators

        df = _make_ohlcv(150)
        df_with_indicators = indicators.calculate_all(df)
        result = build_features(df_with_indicators)
        assert not result.empty

    def test_output_values_are_finite_or_nan(self):
        """build_features() 결과 값이 inf 를 포함하지 않아야 함."""
        from koreanstocks.core.engine.features import build_features, BASE_FEATURE_COLS
        from koreanstocks.core.engine.indicators import indicators

        df = _make_ohlcv(150)
        df_with_indicators = indicators.calculate_all(df)
        result = build_features(df_with_indicators)

        for col in BASE_FEATURE_COLS:
            if col in result.columns:
                assert not np.isinf(result[col].dropna()).any(), \
                    f"{col} 컬럼에 inf 값이 있습니다."


# ─────────────────────────────────────────────────────────────────
# indicators.py — get_composite_score() 범위 검증
# ─────────────────────────────────────────────────────────────────

class TestGetCompositeScore:
    def test_score_in_range_0_to_100(self):
        """기술적 지표 종합 점수는 0 ~ 100 사이여야 함."""
        from koreanstocks.core.engine.indicators import indicators

        df = _make_ohlcv(120)
        df_with_indicators = indicators.calculate_all(df)
        score = indicators.get_composite_score(df_with_indicators)
        assert 0.0 <= score <= 100.0, f"점수 범위 초과: {score}"

    def test_score_returns_float(self):
        """get_composite_score() 는 float 를 반환해야 함."""
        from koreanstocks.core.engine.indicators import indicators

        df = _make_ohlcv(120)
        df_with_indicators = indicators.calculate_all(df)
        score = indicators.get_composite_score(df_with_indicators)
        assert isinstance(score, float)

    def test_score_bullish_gt_bearish(self):
        """상승 추세 데이터의 점수 > 하락 추세 데이터의 점수 (방향성 검증)."""
        from koreanstocks.core.engine.indicators import indicators

        n = 120
        rng = pd.date_range("2024-01-01", periods=n, freq="B")

        bullish_prices = np.linspace(8_000, 12_000, n)
        df_bull = pd.DataFrame(
            {"open": bullish_prices, "high": bullish_prices * 1.01,
             "low": bullish_prices * 0.99, "close": bullish_prices,
             "volume": np.full(n, 1_000_000)}, index=rng
        )

        bearish_prices = np.linspace(12_000, 8_000, n)
        df_bear = pd.DataFrame(
            {"open": bearish_prices, "high": bearish_prices * 1.01,
             "low": bearish_prices * 0.99, "close": bearish_prices,
             "volume": np.full(n, 1_000_000)}, index=rng
        )

        bull_score = indicators.get_composite_score(indicators.calculate_all(df_bull))
        bear_score = indicators.get_composite_score(indicators.calculate_all(df_bear))
        assert bull_score > bear_score, \
            f"상승({bull_score:.1f}) > 하락({bear_score:.1f}) 조건 실패"

    def test_empty_df_returns_default(self):
        """빈 DataFrame 입력 시 기본값(50.0) 반환 (예외 미발생)."""
        from koreanstocks.core.engine.indicators import indicators

        score = indicators.get_composite_score(pd.DataFrame())
        assert score == 50.0


# ─────────────────────────────────────────────────────────────────
# fundamental_provider.py — calc_roe_avg
# ─────────────────────────────────────────────────────────────────

class TestCalcRoeAvg:
    def test_avg_when_both_available(self):
        from koreanstocks.core.data.fundamental_provider import calc_roe_avg
        result = calc_roe_avg({"roe": 10.0, "roe_prev": 20.0})
        assert result == pytest.approx(15.0)

    def test_cur_only_when_prev_missing(self):
        from koreanstocks.core.data.fundamental_provider import calc_roe_avg
        result = calc_roe_avg({"roe": 10.0})
        assert result == pytest.approx(10.0)

    def test_none_when_both_missing(self):
        from koreanstocks.core.data.fundamental_provider import calc_roe_avg
        result = calc_roe_avg({})
        assert result is None

    def test_rounds_to_1_decimal(self):
        from koreanstocks.core.data.fundamental_provider import calc_roe_avg
        result = calc_roe_avg({"roe": 10.333, "roe_prev": 20.777})
        assert result == pytest.approx(round((10.333 + 20.777) / 2, 1))
