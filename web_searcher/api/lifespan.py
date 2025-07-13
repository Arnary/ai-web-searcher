from contextlib import asynccontextmanager
from fastapi import FastAPI
from playwright.async_api import async_playwright

from web_searcher.session import SessionManager

session_manager = SessionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    # global browser
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)

    # Initialize session manager
    await session_manager.initialize(browser)

    yield

    # Shutdown
    print("[INFO] Shutting down - closing all sessions...")
    await session_manager.close_all_sessions()

    if browser:
        await browser.close()
