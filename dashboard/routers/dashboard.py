from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from dashboard.services.dashboard_service import DashboardService
from dashboard.dependencies import get_db, get_exchange_cache, verify

router = APIRouter()
templates = Jinja2Templates(directory="dashboard/templates")

@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    auth: str = Depends(verify),
    db = Depends(get_db),
    exchange_cache = Depends(get_exchange_cache)
):
    service = DashboardService(db, exchange_cache)
    context = service.build_dashboard_context()

    return templates.TemplateResponse(
        "index.html",
        {"request": request, **context}
    )