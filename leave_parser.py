import json
import re


# ============================================================
# 2. JSON Parser
# ============================================================

def parse_action_result(result) -> dict:

    if hasattr(result, "content"):
        result = result.content

    result = str(result).strip()

    result = re.sub(
        r"```json\s*",
        "",
        result,
        flags=re.IGNORECASE
    )

    result = re.sub(
        r"```",
        "",
        result
    ).strip()

    match = re.search(
        r"\{.*\}",
        result,
        re.DOTALL
    )

    if not match:
        raise ValueError(
            f"JSON 결과를 찾을 수 없습니다: {result}"
        )

    return json.loads(
        match.group(0)
    )
