import json
import re



# ============================================================
# 4. DB 결과 → LeaveItem
# ============================================================

def convert_leave_items(
    result
) -> list[LeaveItem]:

    items = []

    if not result:
        return items

    if isinstance(result, dict):
        return items

    for row in result:

        items.append(

            LeaveItem(

                request_id=int(
                    row["request_id"]
                ),

                employee_id=str(
                    row["employee_id"]
                ),

                name=str(
                    row["name"]
                ),

                department=str(
                    row["department"]
                ),

                position=str(
                    row["position"]
                ),

                start_date=str(
                    row["start_date"]
                ),

                end_date=str(
                    row["end_date"]
                ),

                leave_days=int(
                    row["leave_days"]
                ),

                reason=str(
                    row["reason"] or ""
                ),

                status=str(
                    row["status"]
                )
            )
        )

    return items
