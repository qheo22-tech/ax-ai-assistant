import json
import re


def parse_action_result(result) -> dict:

    if hasattr(result, "content"):
        result = result.content

    result = str(result).strip()

    # 코드블록 제거
    match = re.search(
        r"```(?:json)?\s*(.*?)\s*```",
        result,
        re.DOTALL | re.IGNORECASE
    )

    if match:
        result = match.group(1).strip()

    # JSON 시작 위치 찾기
    start = result.find("{")

    if start == -1:
        raise ValueError(
            f"JSON 결과를 찾을 수 없습니다: {result}"
        )

    # 중첩 JSON까지 정상적으로 파싱
    decoder = json.JSONDecoder()

    try:
        data, _ = decoder.raw_decode(
            result[start:]
        )
    except json.JSONDecodeError as e:
        raise ValueError(
            f"JSON 파싱 실패: {e}\n결과: {result}"
        )

    print("[LEAVE PARSED JSON]")
    print(json.dumps(
        data,
        ensure_ascii=False,
        indent=2
    ))

    return data