import os

from fastapi import FastAPI

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))

app = FastAPI()


@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI!"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
