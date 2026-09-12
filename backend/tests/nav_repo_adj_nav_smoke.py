import os
import sys
import atexit

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import init_database
from repositories.nav_repo import NavRepo
from smoke_cleanup import cleanup_fund_codes


def main() -> int:
    init_database()
    nav_repo = NavRepo()
    wind_code = "ADJ.NAV.TEST"
    cleanup_fund_codes([wind_code])
    atexit.register(cleanup_fund_codes, [wind_code])

    rows = [
        {
            "date": "2026-09-07",
            "unit_nav": 1.05,
            "nav": 1.05,
            "accum_nav": 1.05,
            "adj_nav": 1.05,
            "daily_return": None,
        },
        {
            "date": "2026-09-08",
            "unit_nav": 1.0,
            "nav": 1.0,
            "accum_nav": 1.05,
            "adj_nav": 1.05,
            "daily_return": 0.0,
        },
        {
            "date": "2026-09-09",
            "unit_nav": 1.01,
            "nav": 1.01,
            "accum_nav": 1.06,
            "adj_nav": 1.0605,
            "daily_return": 0.01,
        },
    ]
    if not nav_repo.upsert_nav_series(wind_code, rows, replace_range=True):
        raise AssertionError("upsert_nav_series failed for adj_nav fixture")

    series = nav_repo.get_nav_series(wind_code)
    if [str(item.get("date")) for item in series] != ["2026-09-07", "2026-09-08", "2026-09-09"]:
        raise AssertionError(f"nav series order mismatch: {series}")
    expected_adj = [1.05, 1.05, 1.0605]
    for item, expected in zip(series, expected_adj):
        actual = item.get("adj_nav")
        if actual is None or abs(float(actual) - expected) > 1e-4:
            raise AssertionError(f"adj_nav must round-trip through fund_nav: {item} vs {expected}")

    rows[2]["adj_nav"] = 1.061
    if not nav_repo.upsert_nav_series(wind_code, [rows[2]]):
        raise AssertionError("upsert conflict update failed for adj_nav")
    updated = nav_repo.get_nav_series(wind_code)
    if abs(float(updated[-1].get("adj_nav")) - 1.061) > 1e-4:
        raise AssertionError(f"adj_nav conflict update must overwrite: {updated[-1]}")

    print("OK nav_repo persists adj_nav with upsert semantics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
