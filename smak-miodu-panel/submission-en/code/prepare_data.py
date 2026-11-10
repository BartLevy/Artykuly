"""Loading of the blind consumer panel data (data/badania-2.xlsx, sheets "Badania" and "Wyniki").

The source workbook is in Polish; sheet names and answer codes are read as they are.
Missing answers stay missing (None); the analysis uses the available data only.
"""

from dataclasses import asdict
from numbers import Number
from pathlib import Path

from openpyxl import Workbook, load_workbook

from data_model import DataModel


def get_excel_sheet(path: str | Path, sheet_name: str | None = None):
    wb = load_workbook(path, data_only=True)
    return wb[sheet_name] if sheet_name else wb.active


def parse_number_from_cell(cell) -> int | None:
    """'2 - 25-45' -> 2, '3- za silna' -> 3, empty -> None."""
    if cell is None:
        return None
    s = str(cell).strip()
    if not s:
        return None
    try:
        return int(s[0])
    except ValueError:
        return None


def load_and_merge(fname: str | Path) -> list[DataModel]:
    respondents = get_excel_sheet(fname, "Badania")   # respondent data
    ratings = get_excel_sheet(fname, "Wyniki")        # sample ratings

    resp_by_id: dict[int, tuple] = {
        int(row[0]): row for row in respondents.iter_rows(values_only=True)
        if isinstance(row[0], Number)
    }

    result = []
    for row_res in ratings.iter_rows(values_only=True):
        if not isinstance(row_res[0], Number) or not row_res[1]:
            continue
        row = resp_by_id.get(int(row_res[0]))
        if row is None:
            continue
        result.append(DataModel(
            id=int(row[0]),
            date=row[1],
            age=parse_number_from_cell(row[2]),
            how_often=parse_number_from_cell(row[3]),
            gender=row[4] if row[4] in ("k", "m") else None,
            lot=row_res[1],
            overall_rate=row_res[2],
            sweetness=parse_number_from_cell(row_res[3]),
            acidity=parse_number_from_cell(row_res[4]),
            intensity=parse_number_from_cell(row_res[5]),
            is_typical={"t": 1, "n": 0}.get(row_res[6]),   # t = yes, n = no
            comment=row_res[7],
        ))
    return result


def save_to_excel(records: list[DataModel], output_path: str | Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(list(asdict(DataModel()).keys()))
    for dm in records:
        ws.append(list(asdict(dm).values()))
    wb.save(output_path)
