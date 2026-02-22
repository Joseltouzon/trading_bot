from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Form
from fastapi.responses import RedirectResponse
from db import Database

app = FastAPI()
templates = Jinja2Templates(directory="dashboard/templates")
db = Database()


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):

    stats = db.get_dashboard_stats()
    equity_curve = db.get_equity_curve() or []
    open_positions = db.get_open_positions()
    closed_positions = db.get_recent_closed_positions()
    logs = db.get_recent_logs()
    bot_status = db.get_bot_status()
    performance = db.get_performance_metrics()
    max_drawdown = db.calculate_drawdown(equity_curve)
    drawdown_curve = db.get_drawdown_curve(equity_curve)
    state = db.load_state() or {}

    # ================= ACCOUNT SNAPSHOT =================
    account = db.get_latest_account_snapshot()

    # Si no hay datos todavía
    if not account:
        account = {
            "equity": 0,
            "used_margin": 0,
            "available": 0
        }

    # % capital en uso
    usage_pct = 0
    if account["equity"] > 0:
        usage_pct = round(
            (account["used_margin"] / account["equity"]) * 100,
            2
        )

    # Formateo equity_curve
    for e in equity_curve:
        e["created_at"] = e["created_at"].strftime("%H:%M")
        e["total_balance"] = float(e["total_balance"])


    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "stats": stats,
            "equity_curve": equity_curve,
            "open_positions": open_positions,
            "closed_positions": closed_positions,
            "logs": logs,
            "bot_status": bot_status,
            "performance": performance,
            "max_drawdown": max_drawdown,
            "drawdown_curve": drawdown_curve,
            "state": state,
            "account": account,
            "usage_pct": usage_pct
        }
    )


@app.post("/bot/pause")
def pause_bot():
    state = db.load_state()
    state["paused"] = True
    db.save_state(state)
    return RedirectResponse("/", status_code=303)


@app.post("/bot/resume")
def resume_bot():
    state = db.load_state()
    state["paused"] = False
    db.save_state(state)
    return RedirectResponse("/", status_code=303)


@app.post("/bot/update-settings")
def update_settings(
    risk_pct: float = Form(...),
    max_positions: int = Form(...)
):
    state = db.load_state()
    state["risk_pct"] = risk_pct
    state["max_positions"] = max_positions
    db.save_state(state)
    return RedirectResponse("/", status_code=303)


@app.get("/account")
def account_data():
    return db.get_latest_account_snapshot()