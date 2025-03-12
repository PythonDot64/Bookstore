from cs50 import SQL

from flask import Flask, request, render_template, session, redirect, Response
from flask_session import Session
from typing import Final
from requests_cache import CachedSession
import requests
import werkzeug

from helper import login_required, apology

from werkzeug.security import check_password_hash, generate_password_hash

app: Flask = Flask(__name__)

app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

book_api_session = CachedSession(
    cache_name='cache/api', 
    expire_after=600,
    stale_if_error=True,
)

img_api_session = CachedSession(
    cache_name='cache/img', 
    expire_after=600,
    stale_if_error=True,
)

db: SQL = SQL('sqlite:///bookstore.db')
db.execute(
    'CREATE TABLE IF NOT EXISTS user (\
        id INTEGER PRIMARY KEY AUTOINCREMENT,\
        username TEXT NOT NULL,\
        password TEXT NOT NULL\
    );'
)
db.execute(
    'CREATE TABLE IF NOT EXISTS cart(\
        id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,\
        book_id INTEGER NOT NULL,\
        book_name TEXT NOT NULL,\
        book_author TEXT NOT NULL,\
        book_price NUMERIC NOT NULL,\
        book_year NUMERIC NOT NULL,\
        book_rating REAL NOT NULL,\
        FOREIGN KEY (book_id) REFERENCES books(id),\
        FOREIGN KEY (book_name) REFERENCES books(title),\
        FOREIGN KEY (book_author) REFERENCES books(author),\
        FOREIGN KEY (book_price) REFERENCES books(price),\
        FOREIGN KEY (book_year) REFERENCES books(year),\
        FOREIGN KEY (book_rating) REFERENCES books(rating)\
    );'
)


@app.route('/')
@login_required
def index() -> tuple[str | None, int] | str | None:
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login() -> tuple[str, int] | werkzeug.wrappers.response.Response | str:
    session.clear()
    if request.method == 'GET':
        return render_template('login.html')
    
    username: str | None = request.form.get('username')
    password: str | None = request.form.get('password')

    if not username:
        return apology('Missing username')
    
    if not password:
        return apology('Missing password')
    
    user: list[dict[str, str]] = db.execute('SELECT id, password FROM user WHERE username=?', username)

    if len(user) < 1:
        return apology('User not does not exist')

    if not check_password_hash(user[0]['password'], password):
        return apology('Incorrect password')
    
    session['user_id'] = user[0]['id']

    return redirect('/')


@app.route('/register', methods=['GET', 'POST'])
def register() -> tuple[str, int] | str | werkzeug.wrappers.response.Response:
    session.clear()
    if request.method == 'GET':
        return render_template('register.html')
    
    username: str | None = request.form.get('username')
    password: str | None = request.form.get('password')

    users: list[dict[str, int | str]] = db.execute('SELECT * FROM user')

    if not username:
        return apology('Missing username')
    
    for user in users:
        if user['username'] == username:
            return apology('Username taken')
        
    if not password:
        return apology('Missing password')
    
    if password != request.form.get('confirm'):
        return apology('Confirmation and password don\'t match')
    
    db.execute('INSERT INTO user (username, password) VALUES(?,?)', username, generate_password_hash(password))

    session['user_id'] = db.execute('SELECT id FROM user WHERE username=?', username)[0]['id']

    return redirect('/')


@app.route('/logout')
def logout() -> tuple[str, int] | werkzeug.wrappers.response.Response:
    session.clear()
    return redirect('/login')


@app.route('/search')
@login_required
def search() -> tuple[str | None, int] | str | None:
    search: str | None = request.args.get('q')

    if not search:
        return apology('Missing search query')
    
    book_url: Final = f'https://openlibrary.org/search.json?q={search}'

    response = book_api_session.get(book_url)

    try:
        response_json: dict[str, list[dict[str, str | int | float]]] = response.json()
    except Exception as e:
        return apology(f'{e}', response.status_code)
    try:
        for book in response_json['docs']:
            if 'cover_edition_key' not in book:
                img_response = 'No image available'
                continue
            img_url: str = f'https://covers.openlibrary.org/b/olid/{book["cover_edition_key"]}-M.jpg'
            img_response = img_api_session.get(img_url)
    except Exception as e:
        return apology(f'{e}', img_response.status_code)

    return render_template('search.html', books=response_json['docs'], img=img_response)


@app.route('/details')
@login_required
def details() -> tuple[str | None, int] | werkzeug.wrappers.response.Response:
    return redirect('/')
