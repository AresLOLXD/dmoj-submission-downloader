from pydantic import BaseModel
from dataclasses import dataclass
from datetime import datetime


@dataclass
class User:
    id: int
    username: str
    password_hash: str
    is_admin: bool
    is_active: bool
    created_at: datetime


class UserCreate(BaseModel):
    username: str
    password: str
    is_admin: bool = False
