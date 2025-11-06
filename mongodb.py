# mongodb.py
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session
import os
from dotenv import load_dotenv
from bson.objectid import ObjectId

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGO_URL")
client = MongoClient(MONGO_URI) if MONGO_URI else MongoClient()
# get default db or fallback to 'multimodal_db'
try:
    db = client.get_default_database() or client['multimodal_db']
except Exception:
    db = client['multimodal_db']
users = db['users']

def register_user(name, email, password, profile_image=None):
    """Registers a new user"""
    if users.find_one({"email": email}):
        return {"status": "error", "message": "Email already registered"}
    hashed = generate_password_hash(password)
    user_doc = {
        "name": name,
        "email": email,
        "password": hashed,
        "profile_image": profile_image,
    }
    res = users.insert_one(user_doc)
    user_doc["_id"] = str(res.inserted_id)
    user_doc.pop("password", None)
    return {"status": "success", "user": user_doc}


def login_user(email, password):
    """Verifies login credentials"""
    user = users.find_one({"email": email})
    if not user or not check_password_hash(user.get("password", ""), password):
        return {"status": "error", "message": "Invalid credentials"}
    user_slim = {
        "id": str(user.get("_id")),
        "name": user.get("name"),
        "email": user.get("email"),
        "profile_image": user.get("profile_image"),
    }
    session["user"] = user_slim
    return {"status": "success", "user": user_slim}


def logout_user():
    """Logs out current user"""
    session.pop("user", None)
    return {"status": "success"}


def current_user():
    """Returns current session user if logged in"""
    return session.get("user")
