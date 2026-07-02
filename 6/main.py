from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

# Модели

class UserCreate(BaseModel):
    name: str
    email: str

class User(BaseModel):
    id: int
    name: str
    email: str

# Хранилище

users: list[User] = []
next_id: int = 1

# Маршруты

@app.post("/users", response_model=User, status_code=201)
def create_user(data: UserCreate):
    global next_id
    user = User(id=next_id, name=data.name, email=data.email)
    users.append(user)
    next_id += 1
    return user

@app.get("/users", response_model=list[User])
def get_users():
    return users

@app.get("/users/{user_id}", response_model=User)
def get_user(user_id: int):
    for user in users:
        if user.id == user_id:
            return user
    raise HTTPException(status_code=404, detail="User not found")

@app.put("/users/{user_id}", response_model=User)
def update_user(user_id: int, data: UserCreate):
    for i, user in enumerate(users):
        if user.id == user_id:
            users[i] = User(id=user_id, name=data.name, email=data.email)
            return users[i]
    raise HTTPException(status_code=404, detail="User not found")

@app.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int):
    for i, user in enumerate(users):
        if user.id == user_id:
            users.pop(i)
            return
    raise HTTPException(status_code=404, detail="User not found")