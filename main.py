from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.chat import router as chat_router
from routes.metrics import router as metrics_router
from dotenv import load_dotenv
import os
load_dotenv(dotenv_path=".env")

# print("SERPER:", os.getenv("SERPER_API_KEY"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(metrics_router)

@app.get("/")
async def root():
    return {
        "message": "Ministry Culture Chatbot Running"
    }