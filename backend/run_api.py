from app.config import API_HOST, API_PORT
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.api.main:app", host=API_HOST, port=API_PORT, reload=False)
