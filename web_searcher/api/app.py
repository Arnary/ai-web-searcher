import os
from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from web_searcher.api.routes import router
from web_searcher.api.lifespan import lifespan

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")


app = FastAPI(
    title="AI Web Searcher API",
    description="Web navigation agent using LangGraph and Playwright",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)