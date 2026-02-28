# dashboard/routers/dashboard.py
import secrets
from fastapi import APIRouter, Request, Depends, Response, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from dashboard.services.dashboard_service import DashboardService
from dashboard.dependencies import get_db, get_exchange_cache, verify_session, CORRECT_PASSWORD, SERVER_SESSION_TOKEN, SessionUser  # ✅ SessionUser agregado

router = APIRouter()
templates = Jinja2Templates(directory="dashboard/templates")

# Ruta de Login (Formulario simple)
@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
def login_submit(request: Request, password: str = Form(...)):
    if secrets.compare_digest(password, CORRECT_PASSWORD):
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="auth_token", value=SERVER_SESSION_TOKEN, httponly=True, max_age=3600)
        return response
    return templates.TemplateResponse("login.html", {"request": request, "error": "Contraseña incorrecta"})

# Ruta de Logout
@router.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("auth_token")
    return response

# Dashboard Principal (Protegido)
@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    session: SessionUser = Depends(verify_session),  # ✅ Ahora SessionUser está definido
    db = Depends(get_db),
    exchange_cache = Depends(get_exchange_cache)
):
    service = DashboardService(db, exchange_cache)
    context = service.build_dashboard_context()
    return templates.TemplateResponse("index.html", {"request": request, **context})