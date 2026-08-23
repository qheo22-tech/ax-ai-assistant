import os

from dotenv import load_dotenv

load_dotenv(".env.local")




from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from starlette.middleware.sessions import SessionMiddleware

from datetime import date

import psycopg2
import uvicorn
import gradio as gr

from app import demo as ai_demo


# ============================================================
# FastAPI
# ============================================================

app = FastAPI()


# ============================================================
# Session
# ============================================================

app.add_middleware(
    SessionMiddleware,
    secret_key="ax-company-secret-key"
)


templates = Jinja2Templates(
    directory="templates"
)


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
# 로그인 페이지
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse
)
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
    request: Request,
    employee_id: str = Form(...),
    password: str = Form(...)
):

    print(
        f"[LOGIN] employee_id={employee_id}"
    )

    # --------------------------------------------------------
    # 데모 비밀번호
    # --------------------------------------------------------

    if password != "1234":

        return {
            "message": "로그인 실패"
        }

    # --------------------------------------------------------
    # 로그인 성공
    # --------------------------------------------------------

    request.session["employee_id"] = employee_id

    print(
        f"[LOGIN SUCCESS] employee_id={employee_id}"
    )

    print(
        f"[SESSION] employee_id="
        f"{request.session.get('employee_id')}"
    )

    # --------------------------------------------------------
    # Dashboard 이동
    # --------------------------------------------------------

    return RedirectResponse(
        url="/dashboard",
        status_code=303
    )


# ============================================================
# Dashboard
# ============================================================

@app.get(
    "/dashboard",
    response_class=HTMLResponse
)
def dashboard(
    request: Request
):

    employee_id = request.session.get(
        "employee_id"
    )

    print(
        f"[DASHBOARD] employee_id={employee_id}"
    )

    if not employee_id:

        return RedirectResponse(
            url="/",
            status_code=303
        )

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            SELECT
                employee_id,
                name,
                position
            FROM employee
            WHERE employee_id = %s
            """,
            (employee_id,)
        )

        employee = cursor.fetchone()

        if not employee:

            return RedirectResponse(
                url="/",
                status_code=303
            )

        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "employee_id": employee[0],
                "employee_name": employee[1],
                "employee_position": employee[2]
            }
        )

    finally:

        cursor.close()
        conn.close()


# ============================================================
# 마이페이지
# ============================================================

@app.get(
    "/mypage",
    response_class=HTMLResponse
)
def mypage(request: Request):

    employee_id = request.session.get("employee_id")

    if not employee_id:

        return RedirectResponse(
            url="/",
            status_code=303
        )

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

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

        return templates.TemplateResponse(
            request=request,
            name="mypage.html",
            context={
                "employee": data,
                "leave_requests": leave_requests
            }
        )

    finally:

        cursor.close()
        conn.close()


# ============================================================
# 휴가 신청
# ============================================================

@app.post(
    "/leave/request"
)
def request_leave(
    request: Request,
    start_date: str = Form(...),
    end_date: str = Form(...),
    reason: str = Form("")
):

    employee_id = request.session.get(
        "employee_id"
    )

    print(
        f"[LEAVE REQUEST SESSION] "
        f"employee_id={employee_id}"
    )

    if not employee_id:

        return RedirectResponse(
            url="/",
            status_code=303
        )

    conn = get_db_connection()
    cursor = None

    try:

        cursor = conn.cursor()

        start = date.fromisoformat(
            start_date
        )

        end = date.fromisoformat(
            end_date
        )

        if end < start:

            return (
                "종료일은 시작일보다 빠를 수 없습니다."
            )

        leave_days = (
            end - start
        ).days + 1

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

        print(
            "[LEAVE ERROR]",
            e
        )

        return (
            "휴가 신청 중 오류가 발생했습니다."
        )

    finally:

        if cursor:
            cursor.close()

        conn.close()

    return RedirectResponse(
        url="/leave",
        status_code=303
    )


# ============================================================
# 휴가 페이지
# ============================================================

@app.get(
    "/leave",
    response_class=HTMLResponse
)
def leave_page(request: Request):

    employee_id = request.session.get("employee_id")

    if not employee_id:

        return RedirectResponse(
            url="/",
            status_code=303
        )

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

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

        return templates.TemplateResponse(
            request=request,
            name="leave.html",
            context={
                "employee": data,
                "leave_requests": leave_requests
            }
        )

    finally:

        cursor.close()
        conn.close()


# ============================================================
# Gradio AI
# ============================================================

app = gr.mount_gradio_app(
    app,
    ai_demo,
    path="/ai"
)


# ============================================================
# 서버 실행
# ============================================================

if __name__ == "__main__":

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )