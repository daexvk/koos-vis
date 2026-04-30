from typing import List

from pydantic import BaseModel


class ConnectivityResponse(BaseModel):
    triangles: List[List[int]]
