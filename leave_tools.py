import psycopg2

from typing import Optional, Literal

from langchain_core.tools import tool


# ============================================================
# DB 연결
# ============================================================

def get_db_connection():

    return psycopg2.connect(
        host="127.0.0.1",
        port=5432,
        database="ax_company",
        user="axuser",
        password="axpassword"
    )


# ============================================================
# 휴가 조회 Tool
# ============================================================

@tool
def get_leave_requests(
    status: Optional[
        Literal["PENDING", "APPROVED", "REJECTED"]
    ] = None,

    employee_id: Optional[str] = None,

    start_date: Optional[str] = None,

    end_date: Optional[str] = None
):
    """
    회사 휴가 신청 데이터를 조회한다.

    status:
        PENDING  = 승인 대기
        APPROVED = 승인 완료
        REJECTED = 반려
        None     = 전체 상태

    employee_id:
        특정 직원의 휴가만 조회할 경우 사용.
        예: E001

    start_date:
        이 날짜 이후의 휴가를 조회.
        예: 2026-08-01

    end_date:
        이 날짜 이전의 휴가를 조회.
        예: 2026-08-31

    사용 예시:

    전체 휴가 목록:
    get_leave_requests()

    승인 대기:
    get_leave_requests(status="PENDING")

    승인 완료:
    get_leave_requests(status="APPROVED")

    특정 직원:
    get_leave_requests(employee_id="E001")

    특정 기간:
    get_leave_requests(
        start_date="2026-08-01",
        end_date="2026-08-31"
    )
    """

    conn = get_db_connection()

    try:

        cursor = conn.cursor()

        # ----------------------------------------------------
        # 기본 SQL
        # ----------------------------------------------------

        query = """
            SELECT
                lr.request_id,
                lr.employee_id,
                e.name,
                e.department,
                lr.start_date,
                lr.end_date,
                lr.leave_days,
                lr.reason,
                lr.status,
                lr.created_at
            FROM leave_request lr
            JOIN employee e
              ON lr.employee_id = e.employee_id
            WHERE 1 = 1
        """

        params = []


        # ----------------------------------------------------
        # 상태 조건
        # ----------------------------------------------------

        if status:

            query += """
                AND lr.status = %s
            """

            params.append(status)


        # ----------------------------------------------------
        # 직원 조건
        # ----------------------------------------------------

        if employee_id:

            query += """
                AND lr.employee_id = %s
            """

            params.append(employee_id)


        # ----------------------------------------------------
        # 시작 날짜 조건
        # ----------------------------------------------------

        if start_date:

            query += """
                AND lr.start_date >= %s
            """

            params.append(start_date)


        # ----------------------------------------------------
        # 종료 날짜 조건
        # ----------------------------------------------------

        if end_date:

            query += """
                AND lr.end_date <= %s
            """

            params.append(end_date)


        # ----------------------------------------------------
        # 정렬
        # ----------------------------------------------------

        query += """
            ORDER BY lr.start_date DESC
        """


        print("[LEAVE SQL]")
        print(query)

        print("[LEAVE PARAMS]")
        print(params)


        # ----------------------------------------------------
        # 실행
        # ----------------------------------------------------

        cursor.execute(
            query,
            tuple(params)
        )

        rows = cursor.fetchall()


        # ----------------------------------------------------
        # 결과 변환
        # ----------------------------------------------------

        result = []

        for row in rows:

            result.append({
                "request_id": row[0],
                "employee_id": row[1],
                "name": row[2],
                "department": row[3],
                "start_date": str(row[4]),
                "end_date": str(row[5]),
                "leave_days": row[6],
                "reason": row[7],
                "status": row[8],
                "created_at": str(row[9])
            })


        return result


    except Exception as e:

        print("[LEAVE TOOL ERROR]")
        print(e)

        return {
            "error": "휴가 데이터를 조회하는 중 오류가 발생했습니다."
        }


    finally:

        cursor.close()
        conn.close()


@tool
def approve_leave(request_id: int):
    """
    휴가 신청을 승인한다.
    승인 대기(PENDING) 상태인 휴가만 승인한다.
    """

    conn = get_db_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE leave_request
            SET status = 'APPROVED'
            WHERE request_id = %s
              AND status = 'PENDING'
            """,
            (request_id,)
        )

        updated_count = cursor.rowcount

        conn.commit()

        if updated_count == 0:
            return {
                "success": False,
                "request_id": request_id,
                "message": "승인 대기 중인 휴가를 찾을 수 없습니다."
            }

        return {
            "success": True,
            "request_id": request_id,
            "message": f"{request_id}번 휴가가 승인되었습니다."
        }

    except Exception as e:

        conn.rollback()

        return {
            "success": False,
            "request_id": request_id,
            "message": f"휴가 승인 중 오류가 발생했습니다: {str(e)}"
        }

    finally:

        cursor.close()
        conn.close()



@tool
def reject_leave(request_id: int):
    """
    휴가 신청을 거절한다.
    승인 대기(PENDING) 상태인 휴가만 거절한다.
    """

    conn = get_db_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE leave_request
            SET status = 'REJECTED'
            WHERE request_id = %s
              AND status = 'PENDING'
            """,
            (request_id,)
        )

        updated_count = cursor.rowcount

        conn.commit()

        if updated_count == 0:
            return {
                "success": False,
                "request_id": request_id,
                "message": "승인 대기 중인 휴가를 찾을 수 없습니다."
            }

        return {
            "success": True,
            "request_id": request_id,
            "message": f"{request_id}번 휴가가 거절되었습니다."
        }

    except Exception as e:

        conn.rollback()

        return {
            "success": False,
            "request_id": request_id,
            "message": f"휴가 거절 중 오류가 발생했습니다: {str(e)}"
        }

    finally:
        cursor.close()
        conn.close()
        