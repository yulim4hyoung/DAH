"""경로·설정 로딩 헬퍼. 절대경로를 코드에 박지 않고 여기서 일괄 해석한다."""
from __future__ import annotations
import os
import yaml

# dev/ (레포 루트) = 이 파일(src/paths.py)의 두 단계 상위
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config() -> dict:
    with open(os.path.join(REPO_ROOT, "config.yaml"), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _abs(p: str) -> str:
    return p if os.path.isabs(p) else os.path.join(REPO_ROOT, p)


def results_dir(cfg: dict | None = None) -> str:
    cfg = cfg or load_config()
    d = _abs(cfg["paths"]["results"])
    os.makedirs(d, exist_ok=True)
    return d


def models_dir(cfg: dict | None = None) -> str:
    cfg = cfg or load_config()
    d = _abs(cfg["paths"]["models"])
    os.makedirs(d, exist_ok=True)
    return d


def data_dir() -> str:
    d = os.path.join(REPO_ROOT, "data")
    os.makedirs(d, exist_ok=True)
    return d


def resolve_docs_dir(cli_arg: str | None) -> str | None:
    """--docs-dir 인자 > SENTINEL_DOCS_DIR 환경변수 > None(=results만)."""
    d = cli_arg or os.environ.get("SENTINEL_DOCS_DIR") or None
    if d:
        os.makedirs(d, exist_ok=True)
    return d


# 시나리오 키 -> dev_docu 하위 폴더명
DOCS_SUBDIR = {
    "a2_gnss": "A2_gnss",
    "b2_satcom": "B2_satcom",
    "b3_can": "B3_can",
    "demo": "demo",
    "overview": "00_overview",
}
