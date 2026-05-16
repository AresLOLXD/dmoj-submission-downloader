from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from app import config
from app.database import init_db

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY, max_age=28800)

templates = Jinja2Templates(directory="templates")

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.on_event("startup")
async def startup():
    await init_db()
