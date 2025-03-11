from cs50 import SQL

from darkdetect import isDark
from flask import Flask, request, render_template, session, redirect, Response
from flask_session import Session
import requests

from helper import login_required, apology

from werkzeug.security import check_password_hash, generate_password_hash

app: Flask = Flask(__name__)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

db: SQL = SQL("sqlite:///bookstore.db")


# from finance in pset 10
@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index() -> tuple[str, int] | str:
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login() -> tuple[str, int] | Response:
    session.clear()
    if request.method == "GET":
        return render_template("login.html")
    
    username: str = request.form.get("username")
    password: str = request.form.get("password")

    if not username:
        return apology("Missing username")
    
    if not password:
        return apology("Missing password")
    
    user: list[dict[str, int]] = db.execute("SELECT id, password FROM user WHERE username=?", username)

    if len(user) < 1:
        return apology("User not does not exist")

    if not check_password_hash(user[0]["password"], password):
        return apology("Incorrect password")
    
    session["user_id"] = user[0]["id"]

    return redirect('/')


@app.route("/register", methods=["GET", "POST"])
def register() -> tuple[str, int] | Response:
    session.clear()
    if request.method == "GET":
        return render_template("register.html")
    
    username: str = request.form.get("username")
    password: str = request.form.get("password")

    users: list[dict[str, int | str, str]] = db.execute("SELECT * FROM user")

    if not username:
        return apology("Missing username")
    
    for user in users:
        if user["username"] == username:
            return apology("Username taken")
        
    if not password:
        return apology("Missing password")
    
    if password != request.form.get("confirm"):
        return apology("Confirmation and password don't match")
    
    db.execute("INSERT INTO user (username, password) VALUES(?,?)", username, generate_password_hash(password))

    session["user_id"] = db.execute("SELECT id FROM user WHERE username=?", username)[0]["id"]

    return redirect("/")


@app.route('/logout')
def logout() -> tuple[str, int] | Response:
    session.clear()
    return redirect("/login")


@app.route("/search")
@login_required
def search() -> tuple[str, int] | Response:
    search: str = request.args.get("q")
    print(search)
    
    url: str = f"https://openlibrary.org/search.json?q={search}"

    response: Response = requests.get(url)
    return render_template("search.html", books=response.json()["docs"])
