import os
import sys
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from repositories.data_snapshot_repo import DataSourceSnapshotRepo


def main() -> int:
    repo = DataSourceSnapshotRepo()
    created_ids = []

    try:
        snapshot = repo.create_snapshot(
            source="unit-test",
            dataset="fund_nav",
            coverage_start=date(2026, 1, 1),
            coverage_end=date(2026, 5, 15),
            metadata={"purpose": "smoke"},
        )
        created_ids.append(snapshot.get("id"))
        if not snapshot.get("id"):
            print(f"Expected snapshot id, got: {snapshot}")
            return 1
        if snapshot.get("status") != "running":
            print(f"Expected running status, got: {snapshot}")
            return 1

        updated = repo.mark_success(snapshot["id"], record_count=7, metadata={"done": True})
        if updated.get("status") != "success" or updated.get("record_count") != 7:
            print(f"Expected success update, got: {updated}")
            return 1

        failed = repo.create_snapshot(source="unit-test", dataset="fund_nav")
        created_ids.append(failed.get("id"))
        failed = repo.mark_failure(failed["id"], "boom")
        if failed.get("status") != "failed" or failed.get("error_message") != "boom":
            print(f"Expected failure update, got: {failed}")
            return 1

        latest = repo.get_latest_by_dataset("fund_nav", source="unit-test")
        if not latest or latest.get("dataset") != "fund_nav":
            print(f"Expected latest fund_nav snapshot, got: {latest}")
            return 1

        print("OK data snapshot repository lifecycle")
        return 0
    finally:
        # 测试不得把 unit-test 记录留在生产库，否则污染 /api/data-health/summary。
        for snapshot_id in created_ids:
            if snapshot_id:
                repo.delete_snapshot(snapshot_id)


if __name__ == "__main__":
    raise SystemExit(main())
