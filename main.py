from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="VERU MVP")

@app.get("/")
def root():
    return {"message": "VERU API funcionando"}