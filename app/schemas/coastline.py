from typing import Any, Dict, List

from pydantic import BaseModel


class GeoJsonFeature(BaseModel):
    type: str
    properties: Dict[str, Any]
    geometry: Dict[str, Any]


class FeatureCollectionResponse(BaseModel):
    type: str
    features: List[GeoJsonFeature]
