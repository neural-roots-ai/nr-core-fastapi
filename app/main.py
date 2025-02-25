import uvicorn
from fastapi import FastAPI
from src.authentication.routes import router as auth_router
from src.users.routes import router as users_router
from src.program.routes import router as program_router

app = FastAPI()

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(users_router, prefix="/users", tags=["users"])
app.include_router(program_router, prefix="/program", tags=["program"])

@app.get("/")
def read_root():
    return {"message": "Welcome to FastAPI authentication and authorization example"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)