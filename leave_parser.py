import json
import re

# ============================================================
# 2. JSON Parser
# ============================================================

def parse_action_result(result) -> dict:

    if hasattr(result, "content"):
        result = result.content

    result = str(result).strip()

    # --------------------------------------------------------
    # 1. ```json ... ``` 코드블록이 있으면
    #    첫 번째 JSON 코드블록만 사용
    # --------------------------------------------------------

    match = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        result,
        re.DOTALL | re.IGNORECASE
    )

    if match:
        json_text = match.group(1)

    else:
        # ----------------------------------------------------
        # 2. 코드블록이 없으면 첫 번째 JSON 객체만 추출
        # ----------------------------------------------------

        match = re.search(
            r"\{.*?\}",
            result,
            re.DOTALL
        )

        if not match:
            raise ValueError(
                f"JSON 결과를 찾을 수 없습니다: {result}"
            )

        json_text = match.group(0)


    print("[LEAVE PARSED JSON]")
    print(json_text)


    return json.loads(json_text)