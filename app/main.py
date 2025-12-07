from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.dependencies import get_current_user_from_cookie
from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession

# Import routers
from app.api.v1 import auth, plans, payments, notebooks, notes, export, users, notifications, credits, chat

app = FastAPI(title=settings.APP_NAME)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory="app/templates")

# Include API routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(plans.router, prefix="/api/v1/plans", tags=["Plans"])
app.include_router(payments.router, prefix="/api/v1/payments", tags=["Payments"])
app.include_router(notebooks.router, prefix="/api/v1/notebooks", tags=["Notebooks"])
app.include_router(notes.router, prefix="/api/v1/notes", tags=["Notes"])
app.include_router(export.router, prefix="/api/v1/export", tags=["Export"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["Notifications"])
app.include_router(credits.router, prefix="/api/v1/credits", tags=["Credits"])
app.include_router(chat.router, prefix="/api/v1/notebooks", tags=["Chat"])


# Frontend routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Landing page"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    """Signup page (same as login for OTP-based auth)"""
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/notebooks", response_class=HTMLResponse)
async def notebooks_page(
    request: Request,
    user=Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Notebooks page (protected)"""
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("notebooks.html", {"request": request, "user": user})


@app.get("/notes", response_class=HTMLResponse)
async def notes_page(
    request: Request,
    notebook_id: int = None,
    user=Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Notes page (protected)"""
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("notes.html", {
        "request": request,
        "user": user,
        "notebook_id": notebook_id
    })


@app.get("/all-notes", response_class=HTMLResponse)
async def all_notes_page(
    request: Request,
    user=Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """All notes page (protected)"""
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("all-notes.html", {"request": request, "user": user})


@app.get("/editor", response_class=HTMLResponse)
async def editor_page(
    request: Request,
    note_id: int = None,
    user=Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Note editor page (protected)"""
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("editor.html", {
        "request": request,
        "user": user,
        "note_id": note_id
    })


@app.get("/upload", response_class=HTMLResponse)
async def upload_page(
    request: Request,
    user=Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Upload page (protected)"""
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("upload.html", {"request": request, "user": user})


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    user=Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Profile page (protected)"""
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("profile.html", {"request": request, "user": user})


@app.get("/plans", response_class=HTMLResponse)
async def plans_page(
    request: Request,
    user=Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Plans page"""
    return templates.TemplateResponse("plans.html", {"request": request, "user": user})


@app.get("/notifications", response_class=HTMLResponse)
async def notifications_page(
    request: Request,
    user=Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Notifications page (protected)"""
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("notifications.html", {"request": request, "user": user})


@app.get("/chat", response_class=HTMLResponse)
async def chat_page(
    request: Request,
    notebook_id: int,
    user=Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """Chat page (protected)"""
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "user": user,
        "notebook_id": notebook_id
    })


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
