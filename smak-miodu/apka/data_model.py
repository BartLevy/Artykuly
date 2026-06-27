from dataclasses import dataclass
from datetime import date
from typing import Optional

@dataclass
class DataModel:
    id: Optional[int] = None
    # date: Optional[date] = None
    age: Optional[int] = None
    how_often: Optional[int] = None
    gender: Optional[str] = None
    lot: Optional[str] = None
    overall_rate: Optional[int] = None
    sweetness: Optional[int] = None
    acidity: Optional[int] = None
    intensity: Optional[int] = None
    is_taste_ok: Optional[bool] = None
    authorized : Optional[int] = None
    type_of_honey : Optional[str] = None