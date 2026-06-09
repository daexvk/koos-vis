from __future__ import annotations

from pathlib import Path
import csv

from app.core.config import get_settings
from app.services.cache_service import _safe_path_part

# Source/input path for time-series CSV data. Defaults to input_root/POST.
POST_ROOT = get_settings().paths.timeseries_root

# 표시용 정적 라벨 (데이터가 아닌 메타데이터, nstorm-data-structure.html 기준)
REGION_LABELS = {
    "BUSAN1": "부산 1 (부산항)",
    "BUSAN2": "부산 2",
    "DONGHAE": "동해 (묵호·동해항)",
    "JEJU": "제주 (서귀포)",
    "JINHAE": "진해·마산만",
    "KOREA": "한국 전역 (광역)",
    "MOKPO": "목포",
}
TYPHOON_NAMES = {
    "0314": "매미 (MAEMI)",
    "2211": "힌남노 (HINNAMNOR)",
}
MODEL_LABELS = {
    "SURGE": "폭풍해일",
    "TIDE": "조석",
    "WAVE": "파랑",
}
VARIABLE_LABELS = {
    "FREE_SURFACE": "해수면 변위 (m)",
    "WATER_DEPTH": "수심 (m)",
    "VELOCITY_U": "유속 U (동서, m/s)",
    "VELOCITY_V": "유속 V (남북, m/s)",
    "WAVE_HEIGHT_HM0": "유의파고 Hm0 (m)",
    "MEAN_DIRECTION": "평균 파향 (deg)",
    "MEAN_FREQ_FMOY": "평균 주파수 Fmoy (Hz)",
    "PEAK_FREQ_FPD": "첨두 주파수 Fpd (Hz)",
}


def _variable_label(model: str, variable: str) -> str:
    model_label = MODEL_LABELS.get(model.upper(), model.upper())
    var_label = VARIABLE_LABELS.get(variable, variable)
    return f"{model_label} · {var_label}"


def parse_input_stations(region_key: str) -> list[dict]:
    """POST_ROOT/INPUT/Input.<region_key> 의 <Beginxyz>~<Endxyz> 좌표를 파싱."""
    path = POST_ROOT / "INPUT" / f"Input.{_safe_path_part(region_key)}"
    if not path.exists():
        return []

    stations: list[dict] = []
    inside = False
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("<Beginxyz>"):
                inside = True
                continue
            if line.startswith("<Endxyz>"):
                break
            if not inside:
                continue
            parts = line.split(",")
            if len(parts) < 3:
                continue
            try:
                lon = float(parts[0].strip())
                lat = float(parts[1].strip())
            except ValueError:
                continue
            # 3번째 필드 = station id, 뒤에 "#주석"이 붙을 수 있음
            station_id = parts[2].split("#")[0].strip()
            if not station_id:
                continue
            stations.append({"id": station_id, "lat": lat, "lon": lon})
    return stations


def _scan_variables(scenario_dir: Path, scenario_token: str, region_key: str) -> list[dict]:
    """풍보 디렉토리 하위 <MODEL>/TimeSeries/*.csv 파일명에서 variable 목록을 추출."""
    variables: list[dict] = []
    seen: set[str] = set()
    if not scenario_dir.is_dir():
        return variables

    for model_dir in sorted(scenario_dir.iterdir()):
        ts_dir = model_dir / "TimeSeries"
        if not ts_dir.is_dir():
            continue  # TRACK 등 TimeSeries 없는 디렉토리 스킵
        model = model_dir.name
        model_lower = model.lower()
        prefix = f"{scenario_token}_{model_lower}_{region_key}_"
        for csv_path in sorted(ts_dir.glob("*.csv")):
            name = csv_path.stem
            if not name.startswith(prefix):
                continue
            variable = name[len(prefix):]
            var_id = f"{model_lower}_{variable}"
            if var_id in seen:
                continue
            seen.add(var_id)
            variables.append(
                {
                    "id": var_id,
                    "model": model,
                    "variable": variable,
                    "label": _variable_label(model, variable),
                }
            )
    return variables


def read_timeseries_catalog() -> dict:
    """POST_ROOT 를 직접 스캔하여 지역별 station/풍보/variable 카탈로그를 구성."""
    regions: list[dict] = []
    if not POST_ROOT.is_dir():
        return {"regions": regions}

    for region_dir in sorted(POST_ROOT.iterdir()):
        if not region_dir.is_dir() or region_dir.name == "INPUT":
            continue
        region = region_dir.name
        region_key = region.lower()

        # 풍보 디렉토리(<TYPHOON>_<SCN>)를 태풍/시나리오로 분리
        typhoons: dict[str, list[str]] = {}
        scenario_dirs: list[tuple[str, Path]] = []
        for scn_dir in sorted(region_dir.iterdir()):
            if not scn_dir.is_dir():
                continue
            token = scn_dir.name
            if "_" not in token:
                continue
            typhoon_id, scenario_id = token.split("_", 1)
            typhoons.setdefault(typhoon_id, [])
            if scenario_id not in typhoons[typhoon_id]:
                typhoons[typhoon_id].append(scenario_id)
            scenario_dirs.append((token, scn_dir))

        # variable 목록은 풍보 디렉토리 전체의 합집합
        variables: list[dict] = []
        seen_vars: set[str] = set()
        for token, scn_dir in scenario_dirs:
            for var in _scan_variables(scn_dir, token, region_key):
                if var["id"] in seen_vars:
                    continue
                seen_vars.add(var["id"])
                variables.append(var)

        regions.append(
            {
                "region": region,
                "region_key": region_key,
                "label": REGION_LABELS.get(region, region),
                "typhoons": [
                    {
                        "typhoon_id": tid,
                        "typhoon_name": TYPHOON_NAMES.get(tid),
                        "scenario_ids": sids,
                    }
                    for tid, sids in sorted(typhoons.items())
                ],
                "stations": parse_input_stations(region_key),
                "variables": variables,
            }
        )

    return {"regions": regions}


def read_station_series(
    region_key: str,
    typhoon_id: str,
    scenario_id: str,
    station: str,
    variable: str,
) -> dict | None:
    """원본 CSV에서 해당 station 열을 직접 읽어 시계열을 반환 (캐시 없음)."""
    region_key = _safe_path_part(region_key)
    typhoon_id = _safe_path_part(typhoon_id)
    scenario_id = _safe_path_part(scenario_id)
    station = _safe_path_part(station)
    variable = _safe_path_part(variable)

    if "_" not in variable:
        raise ValueError(f"invalid variable: {variable!r}")
    model_lower, var_name = variable.split("_", 1)
    if not model_lower or not var_name:
        raise ValueError(f"invalid variable: {variable!r}")

    scenario_token = f"{typhoon_id}_{scenario_id}"
    region_dir = region_key.upper()
    region_lower = region_key.lower()
    filename = f"{scenario_token}_{model_lower}_{region_lower}_{var_name}.csv"
    path = (
        POST_ROOT
        / region_dir
        / scenario_token
        / model_lower.upper()
        / "TimeSeries"
        / filename
    )
    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return None
        try:
            col = header.index(station)
        except ValueError:
            return None  # 해당 station 열 없음 → 404

        points: list[dict] = []
        for row in reader:
            if len(row) <= col:
                continue
            t = row[0].strip()
            cell = row[col].strip()
            try:
                value = float(cell) if cell else None
            except ValueError:
                value = None
            points.append({"t": t, "value": value})

    return {
        "model": model_lower.upper(),
        "variable": variable,
        "label": _variable_label(model_lower, var_name),
        "points": points,
    }
