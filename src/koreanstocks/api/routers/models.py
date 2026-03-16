"""모델 신뢰도 라우터 — GET /api/model_health"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Body

from koreanstocks.core.config import config
from koreanstocks.core.constants import MIN_MODEL_AUC

logger = logging.getLogger(__name__)
router = APIRouter(tags=["models"])

# params.json 파일이 저장된 디렉토리 — BASE_DIR 기준 (pipx/PyPI 설치 환경 호환)
PARAMS_DIR = Path(config.BASE_DIR) / "models" / "saved" / "model_params"

_MODEL_CONFIGS = [
    ("random_forest",     "랜덤 포레스트",      "random_forest_params.json"),
    ("gradient_boosting", "그래디언트 부스팅",   "gradient_boosting_params.json"),
    ("lightgbm",          "LightGBM",           "lightgbm_params.json"),
    ("catboost",          "CatBoost",           "catboost_params.json"),
    ("xgboost_ranker",    "XGBoost Ranker",     "xgboost_ranker_params.json"),
    ("tcn",               "TCN (딥러닝)",        "tcn_params.json"),
]

_MIN_AUC_THRESHOLD = MIN_MODEL_AUC  # core/constants.py 단일 소스

# ── 편집 가능 파라미터 명세 (UI 렌더링 + 서버 측 검증 범위 동시 사용) ──
_EDITABLE_PARAMS: dict[str, list[dict]] = {
    "catboost": [
        {"key": "depth",            "type": "int",   "min": 2,   "max": 6,    "step": 1},
        {"key": "l2_leaf_reg",      "type": "float", "min": 1.0, "max": 20.0, "step": 0.5},
        {"key": "min_data_in_leaf", "type": "int",   "min": 20,  "max": 100,  "step": 5},
    ],
    "random_forest": [
        {"key": "max_depth",        "type": "int",   "min": 3,   "max": 7,    "step": 1},
        {"key": "min_samples_leaf", "type": "int",   "min": 20,  "max": 80,   "step": 5},
        {"key": "max_features",     "type": "float", "min": 0.2, "max": 0.8,  "step": 0.05},
    ],
    "gradient_boosting": [
        {"key": "max_depth",        "type": "int",   "min": 1,   "max": 4,    "step": 1},
        {"key": "min_samples_leaf", "type": "int",   "min": 15,  "max": 60,   "step": 5},
        {"key": "subsample",        "type": "float", "min": 0.5, "max": 1.0,  "step": 0.05},
    ],
    "lightgbm": [
        {"key": "max_depth",         "type": "int",   "min": 1,   "max": 4,    "step": 1},
        {"key": "min_child_samples", "type": "int",   "min": 50,  "max": 200,  "step": 10},
        {"key": "reg_lambda",        "type": "float", "min": 1.0, "max": 15.0, "step": 0.5},
    ],
    "xgboost_ranker": [
        {"key": "max_depth",        "type": "int",   "min": 2,   "max": 5,    "step": 1},
        {"key": "min_child_weight", "type": "int",   "min": 15,  "max": 60,   "step": 5},
        {"key": "reg_lambda",       "type": "float", "min": 1.0, "max": 10.0, "step": 0.5},
    ],
    "tcn": [],  # 조정 불가 (딥러닝 아키텍처 직접 수정 필요)
}


def _days_since(saved_at: str) -> int:
    """저장 시각(ISO 문자열) → 현재까지 경과 일수."""
    try:
        dt = datetime.fromisoformat(saved_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        return max(0, (now - dt).days)
    except Exception:
        return -1


def _load_model_info(name: str, label: str, filename: str) -> dict | None:
    """단일 모델 params.json 로드 및 집계."""
    path = PARAMS_DIR / filename
    if not path.exists():
        logger.warning(f"model params not found: {path}")
        return None
    try:
        with open(path, encoding="utf-8") as f:
            p = json.load(f)
    except Exception as e:
        logger.error(f"params 로드 실패 [{filename}]: {e}")
        return None

    # null 값 방어 — p.get(key, default)는 키가 존재하고 값이 null이면 None 반환
    _raw_auc = p.get("test_auc")
    test_auc  = float(_raw_auc) if _raw_auc is not None else 0.0
    _raw_cv  = p.get("cv_auc_mean")
    cv_mean   = float(_raw_cv)  if _raw_cv  is not None else 0.0
    saved_at  = p.get("saved_at") or ""
    model_type = p.get("model_type", "binary_classifier")
    # ranker는 test_logloss=None으로 저장됨 (log_loss 미정의)
    raw_logloss = p.get("test_logloss")
    test_logloss = float(raw_logloss) if raw_logloss is not None else None

    _raw_overfit = p.get("overfit_gap")
    overfit_gap  = float(_raw_overfit) if _raw_overfit is not None else 0.0

    architecture = p.get("architecture", "")  # TCN 등 딥러닝 모델 구분용
    # Log Loss 라벨: ranker → "N/A (ranker)", TCN → "N/A (딥러닝 BCE)", 그 외 → 값
    if test_logloss is None:
        logloss_label = "N/A (딥러닝 BCE)" if architecture else "N/A (ranker)"
    else:
        logloss_label = None  # JS에서 값으로 표시

    return {
        "name":               name,
        "label":              label,
        "model_type":         model_type,
        "architecture":       architecture,
        "test_auc":           test_auc,
        "train_auc":          p.get("train_auc", 0.0),
        "cv_auc_mean":        cv_mean,
        "cv_auc_std":         p.get("cv_auc_std", 0.0),
        "overfit_gap":        overfit_gap,
        "regime_gap":         round(test_auc - cv_mean, 4),
        "test_logloss":       test_logloss,
        "logloss_label":      logloss_label,
        "quality_pass":       p.get("quality_pass", False),
        "training_samples":   p.get("training_samples", 0),
        "purging_days":       p.get("purging_days", 0),
        "saved_at":           saved_at,
        "days_since_training": _days_since(saved_at),
        "training_duration":  p.get("training_duration", 0.0),
        "feature_importances": p.get("feature_importances", []),
        "parameters":          p.get("parameters", {}),
        "has_override":        (PARAMS_DIR / f"{name}_overrides.json").exists(),
    }


def _compute_ensemble(models: list[dict]) -> dict:
    """앙상블 집계 및 드리프트 등급 산출."""
    active    = [m for m in models if m is not None]
    n         = len(active)
    total_cfg = len(_MODEL_CONFIGS)   # 설정된 전체 모델 수 (파일 유무 무관)

    if n == 0:
        return {
            "active_count":       0,
            "total_model_count":  total_cfg,
            "tcn_active":         False,
            "mean_test_auc":      0.0,
            "mean_overfit_gap":   0.0,
            "mean_regime_gap":    0.0,
            "all_quality_pass":   False,
            "min_auc_threshold":  _MIN_AUC_THRESHOLD,
            "days_since_training": -1,
            "drift_level":        "HIGH",
            "drift_factors":      ["모델 파일 없음"],
            "retrain_recommended": True,
        }

    tcn_model        = next((m for m in active if m["name"] == "tcn"), None)
    tree_models      = [m for m in active if m["name"] != "tcn"]
    mean_test_auc    = round(sum(m["test_auc"]    for m in active) / n, 4)
    # TCN은 학습 전체 수렴 특성상 train AUC가 높아 overfit_gap이 구조적으로 크게 나타남.
    # 트리 모델과 같은 기준으로 경보를 발령하면 오탐이 발생하므로
    # mean_overfit_gap 계산에서 TCN을 제외한다.
    _gap_models      = tree_models if tree_models else active
    mean_overfit_gap = round(sum(m["overfit_gap"] for m in _gap_models) / len(_gap_models), 4)
    mean_regime_gap  = round(sum(m["regime_gap"]  for m in active) / n, 4)
    all_quality_pass  = all(m["quality_pass"] for m in active)
    any_date_unknown  = any(m["days_since_training"] == -1 for m in active)
    valid_days        = [m["days_since_training"] for m in active if m["days_since_training"] != -1]
    days_since        = max(valid_days) if valid_days else -1

    # 드리프트 등급 결정
    factors: list[str] = []
    retrain = False

    if any_date_unknown:
        factors.append("일부 모델의 학습 날짜 정보 없음 (saved_at 파싱 실패) — 재학습 권장")
        retrain = True
    if days_since != -1 and days_since > 30:
        factors.append(f"마지막 학습 {days_since}일 경과 (권장: 30일 이내)")
        retrain = True
    if mean_overfit_gap > 0.10:
        factors.append(f"트리 모델 평균 과적합 갭 {mean_overfit_gap:.4f} (임계: 0.10, TCN 제외)")
        retrain = True
    if not all_quality_pass:
        factors.append(f"품질 기준 미달 모델 존재 (AUC < {_MIN_AUC_THRESHOLD})")
        retrain = True

    if retrain:
        drift_level = "HIGH"
    elif (days_since != -1 and days_since > 14) or mean_regime_gap > 0.07:
        drift_level = "MEDIUM"
        if days_since != -1 and days_since > 14:
            factors.append(f"마지막 학습 {days_since}일 경과 (권장: 14일 이내)")
        if mean_regime_gap > 0.07:
            factors.append(f"레짐 갭 {mean_regime_gap:.4f} > 0.07 (시장 의존도 주의)")
    else:
        drift_level = "LOW"

    return {
        "active_count":       n,
        "total_model_count":  total_cfg,
        "tcn_active":         tcn_model is not None,
        "tcn_test_auc":       tcn_model["test_auc"]    if tcn_model else None,
        "tcn_cv_auc":         tcn_model["cv_auc_mean"] if tcn_model else None,
        "tcn_overfit_gap":    tcn_model["overfit_gap"] if tcn_model else None,
        "tcn_quality_pass":   tcn_model["quality_pass"] if tcn_model else None,
        "tree_mean_test_auc": round(sum(m["test_auc"] for m in tree_models) / len(tree_models), 4) if tree_models else None,
        "mean_test_auc":      mean_test_auc,
        "mean_overfit_gap":   mean_overfit_gap,
        "mean_regime_gap":    mean_regime_gap,
        "all_quality_pass":   all_quality_pass,
        "min_auc_threshold":  _MIN_AUC_THRESHOLD,
        "days_since_training": days_since,
        "drift_level":        drift_level,
        "drift_factors":      factors,
        "retrain_recommended": retrain,
    }


@router.get("/model_health")
def get_model_health():
    """ML 모델 신뢰도 및 앙상블 상태 반환."""
    models = []
    for name, label, filename in _MODEL_CONFIGS:
        info = _load_model_info(name, label, filename)
        if info:
            models.append(info)

    ensemble = _compute_ensemble(models)

    return {
        "models": models,
        "ensemble": ensemble,
        "scoring_formula": {
            "with_ml_macro": "tech×0.35 + ml×0.35 + 종목감성×0.20 + 거시감성×0.10",
            "with_ml":       "tech×0.40 + ml×0.35 + 종목감성×0.25",
            "without_ml":    "tech×0.65 + 종목감성×0.35",
        },
    }


# ── 파라미터 오버라이드 CRUD ─────────────────────────────────────────────

@router.get("/model_params/{model_name}")
def get_model_params(model_name: str):
    """학습된 파라미터 + 오버라이드 + 편집 가능 키 반환."""
    cfg = next((c for c in _MODEL_CONFIGS if c[0] == model_name), None)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"모델 없음: {model_name}")
    name, label, filename = cfg

    params_path = PARAMS_DIR / filename
    if not params_path.exists():
        raise HTTPException(status_code=404, detail="params.json 없음 — 먼저 학습을 실행하세요")
    try:
        with open(params_path, encoding="utf-8") as f:
            p = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"params 로드 실패: {e}")

    override_path = PARAMS_DIR / f"{name}_overrides.json"
    override = None
    if override_path.exists():
        try:
            with open(override_path, encoding="utf-8") as f:
                override = json.load(f)
        except Exception:
            override = None

    editable = _EDITABLE_PARAMS.get(name, [])
    return {
        "name":         name,
        "label":        label,
        "parameters":   p.get("parameters", {}),
        "override":     override,
        "has_override": override is not None,
        "editable_keys": editable,
        "adjustable":   bool(editable),
    }


@router.post("/model_params/{model_name}")
def save_model_params_override(
    model_name: str,
    body: dict = Body(...),
):
    """파라미터 오버라이드를 PARAMS_DIR/{name}_overrides.json 에 저장."""
    cfg = next((c for c in _MODEL_CONFIGS if c[0] == model_name), None)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"모델 없음: {model_name}")

    editable = _EDITABLE_PARAMS.get(model_name, [])
    if not editable:
        raise HTTPException(status_code=400, detail="이 모델은 파라미터 조정을 지원하지 않습니다 (TCN)")

    # 범위 검증 — 선언된 범위 밖의 값은 거부
    errors: list[str] = []
    validated: dict = {}
    for spec in editable:
        key = spec["key"]
        if key not in body:
            continue
        val = body[key]
        try:
            val = int(val) if spec["type"] == "int" else float(val)
        except (TypeError, ValueError):
            errors.append(f"{key}: 숫자가 아님")
            continue
        if not (spec["min"] <= val <= spec["max"]):
            errors.append(f"{key}={val} 범위 초과 ({spec['min']}~{spec['max']})")
            continue
        validated[key] = val

    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))

    override_path = PARAMS_DIR / f"{model_name}_overrides.json"
    try:
        with open(override_path, "w", encoding="utf-8") as f:
            json.dump(validated, f, indent=2, ensure_ascii=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"저장 실패: {e}")

    logger.info(f"[model_params] override 저장: {model_name} → {validated}")
    return {"status": "saved", "override": validated}


@router.delete("/model_params/{model_name}/override")
def delete_model_params_override(model_name: str):
    """오버라이드 파일 삭제 — 기본값 복원."""
    cfg = next((c for c in _MODEL_CONFIGS if c[0] == model_name), None)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"모델 없음: {model_name}")

    override_path = PARAMS_DIR / f"{model_name}_overrides.json"
    if not override_path.exists():
        raise HTTPException(status_code=404, detail="오버라이드 파일 없음")
    override_path.unlink()
    logger.info(f"[model_params] override 삭제: {model_name}")
    return {"status": "deleted"}
