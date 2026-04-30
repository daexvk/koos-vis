from typing import List, Optional

from pydantic import BaseModel


class TimeItem(BaseModel):
    time_index: int
    time_value: str


class TimeListResponse(BaseModel):
    source_file: Optional[str] = None
    time_indices: List[int]
    times: List[TimeItem]
