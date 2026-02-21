from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
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

    for e in equity_curve:
        e["created_at"] = e["created_at"].strftime("%H:%M")

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "stats": stats,
            "equity_curve": equity_curve,
            "open_positions": open_positions,
            "closed_positions": closed_positions,
            "logs": logs,
            "bot_status": bot_status
        }
    )