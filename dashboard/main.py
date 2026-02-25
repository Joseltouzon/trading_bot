from fastapi import FastAPI
from dashboard.routers import dashboard, api, config

app = FastAPI()

app.include_router(dashboard.router)
app.include_router(api.router)
app.include_router(config.router)