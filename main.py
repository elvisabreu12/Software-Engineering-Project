from fastapi import FastAPI

app = FastAPI()

@app.get("/Hi")
def read_root():
    return {"message": "White Rabbit is running"}