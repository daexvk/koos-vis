from typing import TypedDict

import numpy as np


class TimestepData(TypedDict):
    time: float
    ds: dict[str, np.ndarray]
    triangles: np.ndarray
