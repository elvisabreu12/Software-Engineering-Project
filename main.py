from fastapi import FastAPI

app = FastAPI()

@app.get("/hello-world")
def hello_world():
    return {"message": "Welcome to White Rabbit API!"}
