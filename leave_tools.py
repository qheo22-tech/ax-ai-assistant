import os
import psycopg2

from typing import Optional, Literal

from langchain_core.tools import tool


from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from pathlib import Path
import uuid



# ============================================================
# DB 연결
# ============================================================

def get_db_connection():

    return psycopg2.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "ax_company"),
        user=os.getenv("DB_USER", "axuser"),
        password=os.getenv("DB_PASSWORD", "axpassword")
    )



# ============================================================
# 로그인 사용자 정보 조회
# ============================================================

def get_actor(cursor, actor_employee_id):

    cursor.execute(
        """
        SELECT
            employee_id,
            name,
            department,
            role_id
        FROM employee
        WHERE employee_id = %s
        """,
        (actor_employee_id,)
    )

    return cursor.fetchone()


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

    end_date: Optional[str] = None,

    actor_employee_id: str = None,

    scope: Optional[Literal["self", "team", "all","employee"]] = "self"
):
    """
    로그인한 사용자의 권한에 따라 휴가 신청 데이터를 조회한다.

    권한:

    USER(1)
        - 자신의 휴가만 조회 가능

    MANAGER(2)
        - 자신의 팀(department) 휴가 조회 가능

    ADMIN(3)
        - 전체 직원의 휴가 조회 가능


    status:
        PENDING  = 승인 대기
        APPROVED = 승인 완료
        REJECTED = 반려
        None     = 전체 상태

    employee_id:
        특정 직원의 휴가만 조회할 경우 사용.
        단, 로그인 사용자의 권한 범위를 벗어나는 직원은 조회할 수 없음.

    start_date:
        이 날짜 이후의 휴가를 조회.

    end_date:
        이 날짜 이전의 휴가를 조회.
    """

    conn = get_db_connection()

    cursor = None

    try:

        cursor = conn.cursor()

        # ====================================================
        # 1. 로그인 사용자 조회
        # ====================================================

        actor = get_actor(
            cursor,
            actor_employee_id
        )

        if not actor:

            return {
                "error": "로그인 사용자를 찾을 수 없습니다."
            }

        actor_id = actor[0]
        actor_name = actor[1]
        actor_department = actor[2]
        role_id = actor[3]

        # 관리자(3)는 휴가 조회 시 항상 전체 직원 기준
        if role_id == 3 and not employee_id:
            scope = "all"

            print(
                f"[ADMIN SCOPE OVERRIDE] "
                f"actor={actor_id}, "
                f"scope={scope}, "
                f"status={status}"
            )

        print(
            f"[LEAVE ACCESS] "
            f"employee={actor_id}, "
            f"name={actor_name}, "
            f"department={actor_department}, "
            f"role={role_id}"
        )


        # ====================================================
        # 2. 기본 SQL
        # ====================================================

        query = """
            SELECT
                lr.request_id,
                lr.employee_id,
                e.name,
                e.department,
                e.position,
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


        # ====================================================
        # 3. 권한 + 조회 대상 결정
        # ====================================================

        # 특정 직원 ID가 지정된 경우
        # employee_id를 최우선으로 처리한다.
        #
        # scope=self 라도
        # "E002 휴가 보여줘"처럼 특정 직원이 지정되었다면
        # 본인(actor_id) 조건을 먼저 넣으면 안 된다.

        if employee_id:

            # ------------------------------------------------
            # USER
            # ------------------------------------------------

            if role_id == 1:

                if employee_id != actor_id:

                    return {
                        "error": "본인의 휴가만 조회할 수 있습니다."
                    }


            # ------------------------------------------------
            # MANAGER
            # ------------------------------------------------

            elif role_id == 2:

                cursor.execute(
                    """
                    SELECT department
                    FROM employee
                    WHERE employee_id = %s
                    """,
                    (employee_id,)
                )

                target = cursor.fetchone()

                if not target:

                    return {
                        "error": "조회하려는 직원을 찾을 수 없습니다."
                    }

                target_department = target[0]

                if target_department != actor_department:

                    return {
                        "error": "자신의 팀원 휴가만 조회할 수 있습니다."
                    }


            # ------------------------------------------------
            # ADMIN
            # ------------------------------------------------

            elif role_id == 3:

                # ADMIN은 모든 직원 조회 가능
                pass


            else:

                return {
                    "error": "유효하지 않은 사용자 권한입니다."
                }


            # ------------------------------------------------
            # 특정 직원 조건
            # ------------------------------------------------

            query += """
                AND lr.employee_id = %s
            """

            params.append(employee_id)


        # ====================================================
        # 4. 특정 직원이 지정되지 않은 경우
        # ====================================================

        else:

            # ------------------------------------------------
            # USER
            # ------------------------------------------------

            if role_id == 1:

                # USER는 무조건 본인
                query += """
                    AND lr.employee_id = %s
                """

                params.append(actor_id)


            # ------------------------------------------------
            # MANAGER
            # ------------------------------------------------

            elif role_id == 2:

                if scope == "self":

                    # 본인
                    query += """
                        AND lr.employee_id = %s
                    """

                    params.append(actor_id)


                elif scope == "team":

                    # 팀 전체
                    query += """
                        AND e.department = %s
                    """

                    params.append(actor_department)


                elif scope == "all":

                    return {
                        "error": "전체 휴가를 조회할 권한이 없습니다."
                    }


                else:

                    # scope가 이상하면 기본적으로 본인
                    query += """
                        AND lr.employee_id = %s
                    """

                    params.append(actor_id)


            # ------------------------------------------------
            # ADMIN
            # ------------------------------------------------

            elif role_id == 3:

                if scope == "self":

                    # 본인
                    query += """
                        AND lr.employee_id = %s
                    """

                    params.append(actor_id)


                elif scope in ["team", "all"]:

                    # ADMIN은 전체 조회 가능
                    pass


                else:

                    # 기본은 본인
                    query += """
                        AND lr.employee_id = %s
                    """

                    params.append(actor_id)


            else:

                return {
                    "error": "유효하지 않은 사용자 권한입니다."
                }

# ====================================================
# 4. 특정 직원 조회
# ====================================================

        if employee_id:

            # ------------------------------------------------
            # USER
            # ------------------------------------------------

            if role_id == 1:

                if employee_id != actor_id:

                    return {
                        "error": "본인의 휴가만 조회할 수 있습니다."
                    }


            # ------------------------------------------------
            # MANAGER
            # ------------------------------------------------

            elif role_id == 2:

                cursor.execute(
                    """
                    SELECT department
                    FROM employee
                    WHERE employee_id = %s
                    """,
                    (employee_id,)
                )

                target = cursor.fetchone()

                if not target:

                    return {
                        "error": "조회하려는 직원을 찾을 수 없습니다."
                    }

                target_department = target[0]

                if target_department != actor_department:

                    return {
                        "error": "자신의 팀원 휴가만 조회할 수 있습니다."
                    }


            # ------------------------------------------------
            # ADMIN
            # ------------------------------------------------

            elif role_id == 3:

                pass


            # ------------------------------------------------
            # 최종 직원 조건
            # ------------------------------------------------

            query += """
                AND lr.employee_id = %s
            """

            params.append(employee_id)


        # ====================================================
        # 5. 상태 조건
        # ====================================================

        if status:

            query += """
                AND lr.status = %s
            """

            params.append(status)


        # ====================================================
        # 6. 시작 날짜 조건
        # ====================================================

        if start_date:

            query += """
                AND lr.start_date >= %s
            """

            params.append(start_date)


        # ====================================================
        # 7. 종료 날짜 조건
        # ====================================================

        if end_date:

            query += """
                AND lr.end_date <= %s
            """

            params.append(end_date)


        # ====================================================
        # 8. 정렬
        # ====================================================

        query += """
            ORDER BY lr.start_date DESC
        """


        print("[LEAVE SQL]")
        print(query)

        print("[LEAVE PARAMS]")
        print(params)


        # ====================================================
        # 9. 실행
        # ====================================================

        cursor.execute(
            query,
            tuple(params)
        )

        rows = cursor.fetchall()


        # ====================================================
        # 10. 결과 변환
        # ====================================================

        result = []

        for row in rows:

            result.append({
                "request_id": row[0],
                "employee_id": row[1],
                "name": row[2],
                "department": row[3],
                "position": row[4],
                "start_date": str(row[5]),
                "end_date": str(row[6]),
                "leave_days": row[7],
                "reason": row[8],
                "status": row[9],
                "created_at": str(row[10])
            })


        return result


    except Exception as e:

        print("[LEAVE TOOL ERROR]")
        print(e)

        return {
            "error": "휴가 데이터를 조회하는 중 오류가 발생했습니다."
        }


    finally:

        if cursor:
            cursor.close()

        conn.close()


# ============================================================
# 휴가 승인
# ============================================================

@tool
def approve_leave(
    request_id: int,
    actor_employee_id: str
):
    """
    로그인한 사용자가 휴가 신청을 승인한다.

    USER(1)
        - 승인 불가

    MANAGER(2)
        - 자신의 팀원 승인 가능
        - 자신의 휴가 승인 불가

    ADMIN(3)
        - 모든 직원 승인 가능
        - 자신의 휴가 승인 불가

    승인 대상은 PENDING 상태여야 한다.

    승인 처리:
        1. leave_request 상태 변경
        2. leave_balance 사용/잔여 휴가 업데이트
        3. leave_balance_history 이력 저장

    위 3개 작업은 하나의 트랜잭션으로 처리한다.
    """

    conn = get_db_connection()

    cursor = None

    try:

        cursor = conn.cursor()


        # ====================================================
        # 1. 로그인 사용자 조회
        # ====================================================

        actor = get_actor(
            cursor,
            actor_employee_id
        )

        if not actor:

            return {
                "success": False,
                "request_id": request_id,
                "message": "로그인 사용자를 찾을 수 없습니다."
            }

        actor_id = actor[0]
        actor_department = actor[2]
        role_id = actor[3]


        # ====================================================
        # 2. 승인 권한 확인
        # ====================================================

        if role_id not in [2, 3]:

            return {
                "success": False,
                "request_id": request_id,
                "message": "휴가 승인 권한이 없습니다."
            }


        # ====================================================
        # 3. 휴가 신청 조회
        # ====================================================

        cursor.execute(
            """
            SELECT
                lr.request_id,
                lr.employee_id,
                e.department,
                lr.status,
                lr.leave_days
            FROM leave_request lr
            JOIN employee e
              ON lr.employee_id = e.employee_id
            WHERE lr.request_id = %s
            FOR UPDATE
            """,
            (request_id,)
        )

        leave = cursor.fetchone()

        if not leave:

            return {
                "success": False,
                "request_id": request_id,
                "message": "해당 휴가 신청을 찾을 수 없습니다."
            }

        target_employee_id = leave[1]
        target_department = leave[2]
        status = leave[3]
        leave_days = leave[4]


        # ====================================================
        # 4. 자기 휴가 승인 방지
        # ====================================================

        if actor_id == target_employee_id:

            return {
                "success": False,
                "request_id": request_id,
                "message": "자신의 휴가는 승인할 수 없습니다."
            }


        # ====================================================
        # 5. MANAGER 팀 범위 확인
        # ====================================================

        if role_id == 2:

            if actor_department != target_department:

                return {
                    "success": False,
                    "request_id": request_id,
                    "message": "자신의 팀원 휴가만 승인할 수 있습니다."
                }


        # ====================================================
        # 6. 승인 대기 상태 확인
        # ====================================================

        if status != "PENDING":

            return {
                "success": False,
                "request_id": request_id,
                "message": "승인 대기 중인 휴가만 승인할 수 있습니다."
            }


        # ====================================================
        # 7. 휴가 잔액 조회
        # ====================================================

        cursor.execute(
            """
            SELECT
                total_days,
                used_days,
                remaining_days
            FROM leave_balance
            WHERE employee_id = %s
            FOR UPDATE
            """,
            (target_employee_id,)
        )

        balance = cursor.fetchone()

        if not balance:

            return {
                "success": False,
                "request_id": request_id,
                "message": "휴가 잔액 정보를 찾을 수 없습니다."
            }

        total_days = balance[0]
        before_used_days = balance[1]
        before_remaining_days = balance[2]


        # ====================================================
        # 8. 잔여 휴가 확인
        # ====================================================

        if before_remaining_days < leave_days:

            return {
                "success": False,
                "request_id": request_id,
                "message": (
                    f"잔여 휴가가 부족합니다. "
                    f"잔여 {before_remaining_days}일 / "
                    f"신청 {leave_days}일"
                )
            }


        # ====================================================
        # 9. 변경 후 휴가 계산
        # ====================================================

        after_used_days = (
            before_used_days + leave_days
        )

        after_remaining_days = (
            before_remaining_days - leave_days
        )


        # ====================================================
        # 10. leave_request 승인
        # ====================================================

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

        if updated_count == 0:

            conn.rollback()

            return {
                "success": False,
                "request_id": request_id,
                "message": "휴가 승인에 실패했습니다."
            }


        # ====================================================
        # 11. leave_balance 업데이트
        # ====================================================

        cursor.execute(
            """
            UPDATE leave_balance
            SET
                used_days = %s,
                remaining_days = %s
            WHERE employee_id = %s
            """,
            (
                after_used_days,
                after_remaining_days,
                target_employee_id
            )
        )

        balance_updated_count = cursor.rowcount

        if balance_updated_count == 0:

            conn.rollback()

            return {
                "success": False,
                "request_id": request_id,
                "message": "휴가 잔액 업데이트에 실패했습니다."
            }


        # ====================================================
        # 12. 휴가 잔액 이력 저장
        # ====================================================

        cursor.execute(
            """
            INSERT INTO leave_balance_history (
                employee_id,
                request_id,
                change_type,
                change_days,
                before_used_days,
                after_used_days,
                before_remaining_days,
                after_remaining_days,
                changed_by
            )
            VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s
            )
            """,
            (
                target_employee_id,
                request_id,
                "APPROVE",
                leave_days,
                before_used_days,
                after_used_days,
                before_remaining_days,
                after_remaining_days,
                actor_id
            )
        )


        # ====================================================
        # 13. 최종 COMMIT
        # ====================================================

        conn.commit()


        print(
            f"[LEAVE APPROVED] "
            f"request={request_id}, "
            f"employee={target_employee_id}, "
            f"days={leave_days}, "
            f"used={before_used_days}->{after_used_days}, "
            f"remaining={before_remaining_days}->{after_remaining_days}"
        )


        return {
            "success": True,
            "request_id": request_id,
            "message": (
                f"{request_id}번 휴가가 승인되었습니다. "
                f"({leave_days}일 차감)"
            )
        }


    except Exception as e:

        conn.rollback()

        print("[APPROVE LEAVE ERROR]")
        print(e)

        return {
            "success": False,
            "request_id": request_id,
            "message": "휴가 승인 중 오류가 발생했습니다."
        }


    finally:

        if cursor:
            cursor.close()

        conn.close()

# ============================================================
# 휴가 반려
# ============================================================

@tool
def reject_leave(
    request_id: int,
    actor_employee_id: str
):
    """
    로그인한 사용자가 휴가 신청을 반려한다.

    USER(1)
        - 반려 불가

    MANAGER(2)
        - 자신의 팀원 반려 가능
        - 자신의 휴가 반려 불가

    ADMIN(3)
        - 모든 직원 반려 가능
        - 자신의 휴가 반려 불가

    반려 대상은 PENDING 상태여야 한다.
    """

    conn = get_db_connection()

    cursor = None

    try:

        cursor = conn.cursor()


        # ====================================================
        # 1. 로그인 사용자 조회
        # ====================================================

        actor = get_actor(
            cursor,
            actor_employee_id
        )

        if not actor:

            return {
                "success": False,
                "request_id": request_id,
                "message": "로그인 사용자를 찾을 수 없습니다."
            }

        actor_id = actor[0]
        actor_department = actor[2]
        role_id = actor[3]


        # ====================================================
        # 2. 권한 확인
        # ====================================================

        if role_id not in [2, 3]:

            return {
                "success": False,
                "request_id": request_id,
                "message": "휴가 반려 권한이 없습니다."
            }


        # ====================================================
        # 3. 휴가 신청 조회
        # ====================================================

        cursor.execute(
            """
            SELECT
                lr.request_id,
                lr.employee_id,
                e.department,
                lr.status
            FROM leave_request lr
            JOIN employee e
              ON lr.employee_id = e.employee_id
            WHERE lr.request_id = %s
            """,
            (request_id,)
        )

        leave = cursor.fetchone()

        if not leave:

            return {
                "success": False,
                "request_id": request_id,
                "message": "해당 휴가 신청을 찾을 수 없습니다."
            }

        target_employee_id = leave[1]
        target_department = leave[2]
        status = leave[3]


        # ====================================================
        # 4. 자기 휴가 반려 방지
        # ====================================================

        if actor_id == target_employee_id:

            return {
                "success": False,
                "request_id": request_id,
                "message": "자신의 휴가는 반려할 수 없습니다."
            }


        # ====================================================
        # 5. MANAGER 팀 범위 확인
        # ====================================================

        if role_id == 2:

            if actor_department != target_department:

                return {
                    "success": False,
                    "request_id": request_id,
                    "message": "자신의 팀원 휴가만 반려할 수 있습니다."
                }


        # ====================================================
        # 6. PENDING 상태 확인
        # ====================================================

        if status != "PENDING":

            return {
                "success": False,
                "request_id": request_id,
                "message": "승인 대기 중인 휴가만 반려할 수 있습니다."
            }


        # ====================================================
        # 7. 반려
        # ====================================================

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
                "message": "휴가 반려에 실패했습니다."
            }


        return {
            "success": True,
            "request_id": request_id,
            "message": f"{request_id}번 휴가가 반려되었습니다."
        }


    except Exception as e:

        conn.rollback()

        print("[REJECT LEAVE ERROR]")
        print(e)

        return {
            "success": False,
            "request_id": request_id,
            "message": "휴가 반려 중 오류가 발생했습니다."
        }


    finally:

        if cursor:
            cursor.close()

        conn.close()


# ============================================================
# 휴가 신청
# ============================================================

@tool
def request_leave(
    start_date: str,
    end_date: str,
    reason: str = "",
    actor_employee_id: str = None
):
    """
    로그인한 사용자가 휴가를 신청한다.

    start_date:
        휴가 시작일. YYYY-MM-DD 형식

    end_date:
        휴가 종료일. YYYY-MM-DD 형식

    reason:
        휴가 사유

    actor_employee_id:
        로그인한 사용자 ID

    신청 상태:
        PENDING
    """

    from datetime import date

    conn = get_db_connection()
    cursor = None

    try:

        cursor = conn.cursor()

        # ====================================================
        # 1. 로그인 사용자 확인
        # ====================================================

        actor = get_actor(
            cursor,
            actor_employee_id
        )

        if not actor:

            return {
                "success": False,
                "message": "로그인 사용자를 찾을 수 없습니다."
            }

        actor_id = actor[0]
        actor_name = actor[1]


        # ====================================================
        # 2. 날짜 형식 및 존재 여부 확인
        # ====================================================

        try:

            start = date.fromisoformat(
                start_date
            )

            end = date.fromisoformat(
                end_date
            )

        except ValueError:

            return {
                "success": False,
                "message": (
                    "올바른 날짜를 입력해주세요. "
                    "YYYY-MM-DD 형식이어야 합니다."
                )
            }


        # ====================================================
        # 3. 과거 날짜 확인
        # ====================================================

        today = date.today()

        if start < today:

            return {
                "success": False,
                "message": (
                    f"지난 날짜에는 휴가를 신청할 수 없습니다. "
                    f"신청 가능 날짜: {today}"
                )
            }


        # ====================================================
        # 4. 시작일 / 종료일 확인
        # ====================================================

        if end < start:

            return {
                "success": False,
                "message": (
                    "종료일은 시작일보다 빠를 수 없습니다."
                )
            }


        # ====================================================
        # 5. 휴가 일수 계산
        # ====================================================

        leave_days = (
            end - start
        ).days + 1


        # ====================================================
        # 6. 휴가 잔액 조회
        # ====================================================

        cursor.execute(
            """
            SELECT
                total_days,
                used_days,
                remaining_days
            FROM leave_balance
            WHERE employee_id = %s
            FOR UPDATE
            """,
            (actor_id,)
        )

        balance = cursor.fetchone()

        if not balance:

            return {
                "success": False,
                "message": (
                    "휴가 잔액 정보를 찾을 수 없습니다."
                )
            }

        total_days = balance[0]
        used_days = balance[1]
        remaining_days = balance[2]


        # ====================================================
        # 7. 잔여 휴가 확인
        # ====================================================

        if remaining_days < leave_days:

            return {
                "success": False,
                "message": (
                    f"잔여 휴가가 부족합니다. "
                    f"현재 잔여 휴가: {remaining_days}일, "
                    f"신청 휴가: {leave_days}일"
                )
            }


        # ====================================================
        # 8. 동일 기간 중복 신청 확인
        # ====================================================

        cursor.execute(
            """
            SELECT
                request_id,
                start_date,
                end_date,
                status
            FROM leave_request
            WHERE employee_id = %s
              AND status IN ('PENDING', 'APPROVED')
              AND start_date <= %s
              AND end_date >= %s
            """,
            (
                actor_id,
                end,
                start
            )
        )

        duplicate = cursor.fetchone()

        if duplicate:

            return {
                "success": False,
                "message": (
                    f"기존 휴가 신청과 기간이 겹칩니다. "
                    f"(신청번호: {duplicate[0]}, "
                    f"{duplicate[1]} ~ {duplicate[2]})"
                )
            }


        # ====================================================
        # 9. 휴가 신청 INSERT
        # ====================================================

        cursor.execute(
            """
            INSERT INTO leave_request (
                employee_id,
                start_date,
                end_date,
                leave_days,
                reason,
                status
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                'PENDING'
            )
            RETURNING request_id
            """,
            (
                actor_id,
                start,
                end,
                leave_days,
                reason
            )
        )

        request_id = cursor.fetchone()[0]


        # ====================================================
        # 10. COMMIT
        # ====================================================

        conn.commit()


        print(
            f"[LEAVE REQUEST] "
            f"request={request_id}, "
            f"employee={actor_id}, "
            f"name={actor_name}, "
            f"start={start}, "
            f"end={end}, "
            f"days={leave_days}, "
            f"reason={reason}"
        )


        # ====================================================
        # 11. 결과 반환
        # ====================================================

        return {
            "success": True,
            "request_id": request_id,
            "employee_id": actor_id,
            "start_date": str(start),
            "end_date": str(end),
            "leave_days": leave_days,
            "reason": reason,
            "status": "PENDING",
            "message": (
                f"휴가 신청이 완료되었습니다. "
                f"({start} ~ {end}, {leave_days}일)"
            )
        }


    except Exception as e:

        conn.rollback()

        print("[REQUEST LEAVE ERROR]")
        print(e)

        return {
            "success": False,
            "message": (
                "휴가 신청 중 오류가 발생했습니다."
            )
        }


    finally:

        if cursor:
            cursor.close()

        conn.close()

@tool
def get_leave_balance(
    actor_employee_id: str
):
    """
    로그인한 사용자의 휴가 잔액을 조회한다.
    """

    conn = get_db_connection()
    cursor = None

    try:

        cursor = conn.cursor()

        actor = get_actor(
            cursor,
            actor_employee_id
        )

        if not actor:

            return {
                "success": False,
                "message": "로그인 사용자를 찾을 수 없습니다."
            }

        actor_id = actor[0]
        actor_name = actor[1]

        cursor.execute(
            """
            SELECT
                total_days,
                used_days,
                remaining_days
            FROM leave_balance
            WHERE employee_id = %s
            """,
            (actor_id,)
        )

        balance = cursor.fetchone()

        if not balance:

            return {
                "success": False,
                "message": "휴가 잔액 정보를 찾을 수 없습니다."
            }

        return {
            "success": True,
            "employee_id": actor_id,
            "name": actor_name,
            "total_days": balance[0],
            "used_days": balance[1],
            "remaining_days": balance[2]
        }

    except Exception as e:

        print("[GET LEAVE BALANCE ERROR]")
        print(e)

        return {
            "success": False,
            "message": "휴가 잔액 조회 중 오류가 발생했습니다."
        }

    finally:

        if cursor:
            cursor.close()

        conn.close()

@tool
def find_employee(name: str):
    """
    직원 이름으로 직원 정보를 조회한다.
    동명이인이 있는 경우 여러 직원의 정보를 반환한다.
    """
    conn = get_db_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                employee_id,
                name,
                department,
                position
            FROM employee
            WHERE name = %s
            """,
            (name,)
        )

        rows = cursor.fetchall()

        return [
            {
                "employee_id": row[0],
                "name": row[1],
                "department": row[2],
                "position": row[3]
            }
            for row in rows
        ]

    finally:
        cursor.close()
        conn.close()

@tool
def create_leave_excel(leave_data: list[dict]):
    """
    조회된 휴가 데이터를 Excel 파일로 생성한다.
    """

    headers = [
        "신청번호",
        "사번",
        "신청자",
        "부서",
        "직급",
        "시작일",
        "종료일",
        "일수",
        "사유",
        "상태"
    ]

    rows = []

    for item in leave_data:
        rows.append([
            item["request_id"],
            item["employee_id"],
            item["name"],
            item["department"],
            item["position"],
            item["start_date"],
            item["end_date"],
            item["leave_days"],
            item["reason"],
            item["status"]
        ])

    # Excel 생성
    wb = Workbook()
    ws = wb.active
    ws.title = "휴가 목록"

    # 헤더
    ws.append(headers)

    # 데이터
    for row in rows:
        ws.append(row)

    # 헤더 스타일
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    # 컬럼 너비
    widths = [
        10, 12, 12, 15, 10,
        15, 15, 10, 30, 15
    ]

    for index, width in enumerate(widths, start=1):
        ws.column_dimensions[
            chr(64 + index)
        ].width = width

    # 파일 저장
    output_dir = Path("generated_files")
    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    # 파일명 고정
    filename = "휴가자목록조회.xlsx"

    file_path = output_dir / filename

    wb.save(file_path)

    print("[EXCEL CREATED]")
    print(file_path)

    # 결과 반환
    return {
        "success": True,
        "message": "엑셀 파일이 생성되었습니다.",
        "file_path": str(file_path),
        "filename": filename
    }