import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId
from typing import List, Optional

from database import db, create_document, get_documents
from schemas import Task

app = FastAPI(title="Todo API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utility to convert Mongo docs to JSON-serializable dicts

def serialize_doc(doc: dict):
    if not doc:
        return doc
    doc = dict(doc)
    _id = doc.get("_id")
    if isinstance(_id, ObjectId):
        doc["id"] = str(_id)
        del doc["_id"]
    return doc

@app.get("/")
def read_root():
    return {"message": "Todo API running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    return response

# ---- Todo Endpoints ----

COLLECTION = "task"

class TaskCreate(BaseModel):
    title: str

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    completed: Optional[bool] = None

@app.get("/api/tasks")
def list_tasks() -> List[dict]:
    docs = get_documents(COLLECTION, {})
    return [serialize_doc(d) for d in docs]

@app.post("/api/tasks", status_code=201)
def create_task(payload: TaskCreate):
    task = Task(title=payload.title, completed=False)
    inserted_id = create_document(COLLECTION, task)
    created = db[COLLECTION].find_one({"_id": ObjectId(inserted_id)})
    return serialize_doc(created)

@app.patch("/api/tasks/{task_id}")
def update_task(task_id: str, payload: TaskUpdate):
    try:
        oid = ObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task id")

    update = {k: v for k, v in payload.dict(exclude_unset=True).items()}
    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")

    update["updated_at"] = __import__("datetime").datetime.utcnow()

    res = db[COLLECTION].update_one({"_id": oid}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")

    doc = db[COLLECTION].find_one({"_id": oid})
    return serialize_doc(doc)

@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: str):
    try:
        oid = ObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task id")

    res = db[COLLECTION].delete_one({"_id": oid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ok": True}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
