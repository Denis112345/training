from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt

app = FastAPI()
security = HTTPBearer()

#  Настройки 
#  Не стал делать .env так как в ТЗ не было
SECRET_KEY = "my-secret-key"
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 30

#  Модели 

class UserAuth(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    name: str
    email: str

class User(BaseModel):
    id: int
    name: str
    email: str

#  Хранилище 

users: list[User] = []
next_id: int = 1
accounts: dict[str, str] = {}  # {username: password}

#  Работа с токеном 

def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

#  Аутентификация 

@app.post("/register", status_code=201)
def register(data: UserAuth):
    if data.username in accounts:
        raise HTTPException(status_code=400, detail="User already exists")
    accounts[data.username] = data.password
    return {"message": "Registered"}

@app.post("/login")
def login(data: UserAuth):
    if data.username not in accounts or accounts[data.username] != data.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(data.username)
    return {"access_token": token, "token_type": "bearer"}

#  CRUD (защищённые маршруты) 

@app.post("/users", response_model=User, status_code=201)
def create_user(data: UserCreate, username: str = Depends(get_current_user)):
    global next_id
    user = User(id=next_id, name=data.name, email=data.email)
    users.append(user)
    next_id += 1
    return user

@app.get("/users", response_model=list[User])
def get_users(username: str = Depends(get_current_user)):
    return users

@app.get("/users/{user_id}", response_model=User)
def get_user(user_id: int, username: str = Depends(get_current_user)):
    for user in users:
        if user.id == user_id:
            return user
    raise HTTPException(status_code=404, detail="User not found")

@app.put("/users/{user_id}", response_model=User)
def update_user(user_id: int, data: UserCreate, username: str = Depends(get_current_user)):
    for i, user in enumerate(users):
        if user.id == user_id:
            users[i] = User(id=user_id, name=data.name, email=data.email)
            return users[i]
    raise HTTPException(status_code=404, detail="User not found")

@app.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, username: str = Depends(get_current_user)):
    for i, user in enumerate(users):
        if user.id == user_id:
            users.pop(i)
            return
    raise HTTPException(status_code=404, detail="User not found")