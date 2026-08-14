from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from datetime import date

import psycopg2


app = FastAPI()

templates = Jinja2Templates(directory="templates")


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
# 로그인 페이지
# ============================================================

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={}
    )


# ============================================================
# 로그인 처리
# ============================================================

@app.post("/login")
def login(
    employee_id: str = Form(...),
    password: str = Form(...)
):

    print(f"[LOGIN] employee_id={employee_id}")

    # 현재 데모용
    if password != "1234":

        return {
            "message": "로그인 실패"
        }

    return RedirectResponse(
        url=f"/mypage/{employee_id}",
        status_code=303
    )


# ============================================================
# 마이페이지
# ============================================================

@app.get(
    "/mypage/{employee_id}",
    response_class=HTMLResponse
)
def mypage(
    request: Request,
    employee_id: str
):

    conn = get_db_connection()
    cursor = conn.cursor()

    # ============================================================
    # 직원 정보 + 휴가 현황
    # ============================================================

    cursor.execute(
        """
        SELECT
            e.employee_id,
            e.name,
            e.department,
            e.position,
            e.email,
            l.total_days,
            l.used_days,
            l.remaining_days
        FROM employee e
        JOIN leave_balance l
          ON e.employee_id = l.employee_id
        WHERE e.employee_id = %s
        """,
        (employee_id,)
    )

    employee = cursor.fetchone()

    if not employee:

        cursor.close()
        conn.close()

        return {
            "message": "사용자를 찾을 수 없습니다."
        }


    data = {
        "employee_id": employee[0],
        "name": employee[1],
        "department": employee[2],
        "position": employee[3],
        "email": employee[4],
        "total_days": employee[5],
        "used_days": employee[6],
        "remaining_days": employee[7]
    }


    # ============================================================
    # 휴가 신청 이력 조회
    # ============================================================

    cursor.execute(
        """
        SELECT
            request_id,
            employee_id,
            start_date,
            end_date,
            leave_days,
            reason,
            status,
            created_at
        FROM leave_request
        WHERE employee_id = %s
        ORDER BY created_at DESC
        """,
        (employee_id,)
    )

    rows = cursor.fetchall()

    leave_requests = []

    for row in rows:

        leave_requests.append({
            "request_id": row[0],
            "employee_id": row[1],
            "start_date": row[2],
            "end_date": row[3],
            "leave_days": row[4],
            "reason": row[5],
            "status": row[6],
            "created_at": row[7]
        })


    cursor.close()
    conn.close()


    # ============================================================
    # 마이페이지
    # ============================================================

    return templates.TemplateResponse(
        request=request,
        name="mypage.html",
        context={
            "employee": data,
            "leave_requests": leave_requests
        }
    )



# ============================================================
# 휴가 신청
# ============================================================

@app.post("/leave/request/{employee_id}")
def request_leave(
    employee_id: str,
    start_date: str = Form(...),
    end_date: str = Form(...),
    reason: str = Form("")
):

    conn = get_db_connection()

    try:

        cursor = conn.cursor()


        # ----------------------------------------------------
        # 문자열 날짜 → date 객체
        # ----------------------------------------------------

        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)


        # ----------------------------------------------------
        # 날짜 검증
        # ----------------------------------------------------

        if end < start:

            return "종료일은 시작일보다 빠를 수 없습니다."


        # ----------------------------------------------------
        # 휴가 일수 계산
        # ----------------------------------------------------

        leave_days = (end - start).days + 1


        # ----------------------------------------------------
        # DB INSERT
        # ----------------------------------------------------

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
            """,
            (
                employee_id,
                start,
                end,
                leave_days,
                reason
            )
        )


        # ----------------------------------------------------
        # COMMIT
        # ----------------------------------------------------

        conn.commit()

        print(
            f"[LEAVE REQUEST] "
            f"employee={employee_id}, "
            f"start={start}, "
            f"end={end}, "
            f"days={leave_days}, "
            f"reason={reason}"
        )


    except Exception as e:

        conn.rollback()

        print("[LEAVE ERROR]", e)

        return "휴가 신청 중 오류가 발생했습니다."


    finally:

        cursor.close()
        conn.close()


    # --------------------------------------------------------
    # 신청 완료 → 마이페이지
    # --------------------------------------------------------

    return RedirectResponse(
        url=f"/mypage/{employee_id}",
        status_code=303
    )