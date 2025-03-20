import asyncio

from aiohttp_client_cache.session import CachedSession
from aiohttp_client_cache import SQLiteBackend

from cs50 import SQL # type: ignore

from datetime import timedelta

from flask import Flask, request, render_template, session, redirect
from flask_session import Session

from functools import cache

from helper import login_required, apology # type: ignore

from operator import itemgetter

from requests_cache import CachedSession as api_cache

from typing import Any, Final

import werkzeug
from werkzeug.security import check_password_hash, generate_password_hash

app: Flask = Flask(__name__)

app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

general_book_cache = api_cache(
    cache_name='cache/books.db', 
    expire_after=timedelta(days=1),
)

book_id_cache = SQLiteBackend(
    cache_name='/cache/book_word.db',
    expire_after=timedelta(days=1),
)

db: SQL = SQL('sqlite:///bookstore.db')

# db.execute('read create_table.sql'), fix later


@app.route('/')
@login_required
def index() -> str:
    def get_urls(books: Any) -> list[str]:
        urls: list[str] = []

        for i in range(5):
            book = books[i]
            if 'cover_edition_key' not in book:
                urls.append('Image not found')
                continue
            urls.append(f'https://covers.openlibrary.org/b/olid/{book['cover_edition_key']}-S.jpg')
        return urls
    last_search = db.execute('SELECT search FROM last_search WHERE user_id=?', session['user_id'])
    if len(last_search) < 1:
        return render_template('index.html', books='')
    books: Any = general_book_cache.get(last_search[0]['search']).json()['docs']
    return render_template('index.html', books=books, img=get_urls(books))


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
            urls.append(f'https://covers.openlibrary.org/b/olid/{book['cover_edition_key']}-M.jpg')
        return urls

    
    sort_by: str | None= request.args.get('sort')

    if not sort_by:
        return apology('You cannot sort by nothing')

    match sort_by:
        case 'random':
            book_url: str = f'https://www.openlibrary.org/search.json?title={search}&sort=random.hourly'
        case 'rating1':
            book_url: str = f'https://www.openlibrary.org/search.json?title={search}&sort=rating'
        case 'rating2':
            book_url: str = f'https://www.openlibrary.org/search.json?title={search}&sort=rating asc'
        case 'title':
            book_url: str = f'https://www.openlibrary.org/search.json?title={search}&sort=title'
        case 'year':
            book_url: str = f'https://www.openlibrary.org/search.json?title={search}$sort=new'
        case _:
            return apology(f'{sort_by.capitalize} is not allowed')


    db.execute('UPDATE last_search SET search=? WHERE user_id=?', book_url, session['user_id'])
    changes: list[dict[str, int]] = db.execute('SELECT changes();')[0]['changes()']

    if changes == 0:
        db.execute('INSERT INTO last_search (search, user_id) VALUES (?, ?)', book_url, session['user_id'])

    try:     
        response = general_book_cache.get(book_url)
        books: Any = response.json()['docs']
    except Exception as e:
        return apology(f'{e}', 500)
    
    urls: list[str] = get_urls(books)

    return render_template('search.html', books=books, img=urls, length=len(books))


@app.route('/details', methods=['GET', 'POST'])
@login_required
def details() -> tuple[str, int] | str:
    book: str | None = request.form.get('book')
    work: str | None = request.form.get('key')
    img: Final = f'https://covers.openlibrary.org/b/olid/{request.form.get('image')}-L.jpg'

    return render_template('details.html', work=general_book_cache.get(f'https://www.openlibrary.org{work}.json').json(), img=img, id=work, book=book)


@app.route('/cart', methods=['GET', 'POST'])
@login_required
def cart() -> tuple[str, int] | str:
    if request.method == 'POST':
        book_id: str | None = request.form.get('book')
        if not book_id:
            return apology('Missing borrowing book(somehow)')
        if book_id in db.execute('SELECT book_id FROM cart WHERE user_id=?', session['user_id'])[0].values():
            return apology('Book already in cart')
        db.execute('INSERT INTO cart (user_id,book_id) VALUES (?,?)', session['user_id'], book_id)
    cart: list[str] = db.execute('SELECT * FROM cart WHERE user_id=?', session['user_id'])
    return render_template('cart.html', books=cart)
