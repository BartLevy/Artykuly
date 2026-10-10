from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class DataModel:
    """Jedna ocena jednej próbki przez jednego respondenta (badania-2.xlsx)."""
    id: Optional[int] = None
    date: Optional[datetime] = None
    age: Optional[int] = None          # 1: <25, 2: 25–45, 3: 46–65, 4: >65
    how_often: Optional[int] = None    # 1: codziennie, 2: raz w mc, 3: okazyjnie
    gender: Optional[str] = None       # "k" / "m"
    lot: Optional[str] = None
    overall_rate: Optional[int] = None  # 1–5
    sweetness: Optional[int] = None     # 1: za słaba, 2: w sam raz, 3: za silna
    acidity: Optional[int] = None
    intensity: Optional[int] = None
    is_typical: Optional[bool] = None   # „smak typowy dla miodu naturalnego”
    comment: Optional[str] = None       # kolumna „Uwagi”
