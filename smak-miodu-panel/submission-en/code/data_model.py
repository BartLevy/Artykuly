from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class DataModel:
    """One rating of one sample by one respondent (data/badania-2.xlsx)."""
    id: Optional[int] = None
    date: Optional[datetime] = None
    age: Optional[int] = None          # 1: <25, 2: 25-45, 3: 46-65, 4: >65
    how_often: Optional[int] = None    # 1: daily or several times a week, 2: once a month, 3: occasionally
    gender: Optional[str] = None       # "k" (female) / "m" (male), as coded in the sheet
    lot: Optional[str] = None
    overall_rate: Optional[int] = None  # 1-5
    sweetness: Optional[int] = None     # 1: too weak, 2: just right, 3: too strong
    acidity: Optional[int] = None
    intensity: Optional[int] = None
    is_typical: Optional[bool] = None   # "taste typical of natural honey"
    comment: Optional[str] = None       # column "Uwagi" (comments)
