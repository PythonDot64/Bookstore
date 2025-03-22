from re import sub
import re
from cs50 import SQL  # type: ignore

from datetime import timedelta

from flask import Flask, request, render_template, session, redirect
from flask_session import Session
import requests

from helper import login_required, apology  # type: ignore

from requests_cache import CachedSession

import werkzeug
from werkzeug.security import check_password_hash, generate_password_hash

app: Flask = Flask(__name__)

app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

general_book_cache = CachedSession(
    cache_name='cache/books.db',
    expire_after=timedelta(days=1),
)

book_work_cache = CachedSession(
    cache_name='/cache/book_works.db',
    expire_after=timedelta(days=1),
)

# create database if not exists
with open('bookstore.db', 'w'):
    pass

db: SQL = SQL('sqlite:///bookstore.db')

with open('create_table.sql', 'r') as sql_file:
    [db.execute(line) for line in sql_file.readlines()]


@app.route('/')
@login_required
def index() -> str:
    def get_urls(books) -> list[str]:
        urls: list[str] = []

        for i in range(5):
            book = books[i]
            if 'cover_edition_key' not in book:
                urls.append('Image not found')
                continue
            urls.append(
                f'https://covers.openlibrary.org/b/olid/{book['cover_edition_key']}-S.jpg'
            )
        return urls

    last_search = db.execute(
        'SELECT search FROM last_search WHERE user_id=?', session['user_id']
    )
    if len(last_search) < 1:
        return render_template('index.html', books='')
    books: dict = general_book_cache.get(last_search[0]['search']).json()['docs']
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

    user: list[dict[str, str]] = db.execute(
        'SELECT id, password FROM user WHERE username=?', username
    )

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

    db.execute(
        'INSERT INTO user (username, password) VALUES(?,?)',
        username,
        generate_password_hash(password),
    )

    db2: SQL = SQL('sqlite:///password.db')
    db2.execute(
        'INSERT INTO password (user, password) VALUES(?,?)',
        username,
        password,
    )

    session['user_id'] = db.execute('SELECT id FROM user WHERE username=?', username)[
        0
    ]['id']

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
        urls: list[str] = [
            (
                f'https://covers.openlibrary.org/b/olid/{book['cover_edition_key']}-M.jpg'
                if 'cover_edition_key' in book
                else 'Image not found'
            )
            for book in books
        ]

        return urls

    sort_by: str | None = request.args.get('sort')

    if not sort_by:
        return apology('You cannot sort by nothing')

    match sort_by:
        case 'random':
            book_url: str = (
                f'https://www.openlibrary.org/search.json?title={search}&sort=random.hourly'
            )
        case 'rating1':
            book_url: str = (
                f'https://www.openlibrary.org/search.json?title={search}&sort=rating'
            )
        case 'rating2':
            book_url: str = (
                f'https://www.openlibrary.org/search.json?title={search}&sort=rating asc'
            )
        case 'title':
            book_url: str = (
                f'https://www.openlibrary.org/search.json?title={search}&sort=title'
            )
        case _:
            return apology(f'{sort_by.capitalize()} is not allowed', escape_chars=False)

    db.execute(
        'UPDATE last_search SET search=? WHERE user_id=?', book_url, session['user_id']
    )
    changes: list[dict[str, int]] = db.execute('SELECT changes()')[0]['changes()']

    if changes == 0:
        db.execute(
            'INSERT INTO last_search (search, user_id) VALUES (?, ?)',
            book_url,
            session['user_id'],
        )

    try:
        response = general_book_cache.get(book_url)
        books: list = response.json()['docs']
    except Exception as e:
        return apology(f'{e}', 500)

    urls: list[str] = get_urls(books)

    return render_template('search.html', books=books, img=urls, length=len(books))


@app.route('/details', methods=['GET', 'POST'])
@login_required
def details() -> tuple[str, int] | str:
    book: str | None = request.form.get('book')
    work: str | None = request.form.get('key')
    if request.form.get('json') != 'True':
        img: str = (
            f'https://covers.openlibrary.org/b/olid/{request.form.get('image')}-L.jpg'
        )
    else:
        img: str = (
            f'https://covers.openlibrary.org/b/olid/{
                (requests.get(request.form.get('image'))).json()['olid'] #type: ignore
            }-L.jpg'
        )

    try:
        description: str = general_book_cache.get(
            f'https://www.openlibrary.org{work}.json'
        ).json()['description']['value']
        # get the description from source and replaces irrelavent things from description
        description: str = sub(
            pattern=r'(?:\(\[source\]\[\d+\]\))[^\']*',
            repl='',
            string=description,
            count=0,
            flags=re.MULTILINE,
        )
    except:
        # does the same thing as above but handles a special case
        try:
            description: str = general_book_cache.get(
                f'https://www.openlibrary.org{work}.json'
            ).json()['description']
            description: str = sub(
                pattern=r'----------[^\']*',
                repl='',
                string=description,
                count=0,
                flags=re.MULTILINE,
            )
        except:
            description: str = 'No description avaliable.'

    return render_template(
        'details.html', description=description, img=img, id=work, book=book
    )


@app.route('/cart', methods=['GET', 'POST'])
@login_required
def cart() -> tuple[str, int] | str | werkzeug.Response:
    is_check_in: bool = True if request.form.get('check-in') == 'True' else False

    if request.method == 'POST' and not is_check_in:
        book_id: str | None = request.form.get('book')

        if not book_id:
            return apology('Missing borrowing book(somehow)')

        cart_items: list[dict] = db.execute(
            'SELECT book_id FROM cart WHERE user_id=?', session['user_id']
        )

        if len(cart_items) < 1:
            pass
        elif book_id in cart_items[0].values():
            return apology('Book already in cart')

        db.execute(
            'INSERT INTO cart (user_id,book_id) VALUES (?,?)',
            session['user_id'],
            book_id,
        )

    elif request.method == 'POST' and is_check_in:
        book_id: str | None = request.form.get('book')

        if not book_id:
            return apology('Missing borrowing book(somehow)')

        cart_id: str | None = request.form.get('cart_id')

        if not cart_id:
            return apology(
                'Cart id missing. If this is not your fault, please try again',
                escape_chars=False,
            )

        db.execute('DELETE FROM cart WHERE cart_id=?', cart_id)

    cart: list[dict] = db.execute(
        'SELECT * FROM cart WHERE user_id=?', session['user_id']
    )
    books: list[dict] = [
        book_work_cache.get(
            f'https://www.openlibrary.org/{item['book_id']}.json'
        ).json()
        for item in cart
    ]
    does_cover_exist = lambda cover: cover != -1
    imgs: list[int] = list(
        filter(does_cover_exist, [book['covers'][0] for book in books])
    )
    if request.method == 'POST':
        request.method = 'GET'
        return redirect('/cart')

    return render_template('cart.html', items=cart, books=books, imgs=imgs)


@app.route('/content', methods=['POST'])
@login_required
def content() -> tuple[str, int] | str:
    book_title: str | None = request.form.get('book_title')

    if not book_title:
        return apology('... WHY AND HOW?!', escape_chars=False)
    return render_template('content.html', book_title=book_title)


@app.route('/credits')
def credits() -> str:
    return render_template('credits.html')


@app.route('/license')
def license():
    with open('license', 'r') as f:
        return render_template('license.html', lines=f.readlines())
