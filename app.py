from datetime import timedelta
from cs50 import SQL # type: ignore

from flask import Flask, request, render_template, session, redirect
from flask_session import Session
from typing import Final
from requests_cache import CachedSession as api_cache
import werkzeug

from helper import login_required, apology # type: ignore

from werkzeug.security import check_password_hash, generate_password_hash

app: Flask = Flask(__name__)

app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

book_api_session = api_cache(
    cache_name='cache/books.db', 
    expire_after=timedelta(days=1),
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
def index() -> str:
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login() -> tuple[str, int] | werkzeug.wrappers.response.Response | str:
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
def search() -> werkzeug.wrappers.response.Response | tuple[str, int] | str:
    search: str | None = request.args.get('q')
    if not search:
        return apology('Missing search query')

    def get_urls(books: list[dict[str, str | int | float]]) -> list[str]:
        urls: list[str] = []

        for book in books:
            if 'cover_edition_key' not in book:
                urls.append('Image not found')
                continue
            urls.append(f'https://covers.openlibrary.org/b/olid/{book["cover_edition_key"]}-M.jpg')
        return urls

    book_url: Final = f'https://openlibrary.org/search.json?q={search}'


    try:
        response = book_api_session.get(book_url)
        books: list[dict[str, str | int | float]] = response.json()['docs']
    except Exception as e:
        return apology(f'{e}', 500)
    
    urls: list[str] = get_urls(books)

    return render_template('search.html', books=books, img=urls, length=len(books))


@app.route('/details', methods=['GET', 'POST'])
@login_required
def details() -> tuple[str, int] | str:
    i: str | None = request.args.get('key')
    print(i)
    img: str | None = request.args.get('image')
    print(img)

    print(img)

    return render_template('details.html', book=book_api_session.get(f'https://www.openlibrary.org{i}.json').json(), img=img)


@app.route('/cart')
def cart() -> tuple[str, int] | str:
    db.execute("SELECT * FROM cart WHERE user_id=?", session['user_id'])
    return render_template('cart.html')
