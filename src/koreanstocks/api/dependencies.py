"""FastAPI 공통 의존성"""
from koreanstocks.core.data.database import db_manager
from koreanstocks.core.engine.analysis_agent import analysis_agent
from koreanstocks.core.engine.recommendation_agent import recommendation_agent
from koreanstocks.core.data.provider import data_provider
from koreanstocks.core.engine.value_screener import value_screener
from koreanstocks.core.engine.quality_screener import quality_screener


def get_db():
    return db_manager


def get_analysis_agent():
    return analysis_agent


def get_recommendation_agent():
    return recommendation_agent


def get_data_provider():
    return data_provider


def get_value_screener():
    return value_screener


def get_quality_screener():
    return quality_screener
