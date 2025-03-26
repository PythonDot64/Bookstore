from re import sub
import re
from cs50 import SQL  # type: ignore
from os import system

from datetime import timedelta

from flask import Flask, request, render_template, session, redirect
from flask_session import Session
import requests

from helper import login_required, apology  # type: ignore

from requests_cache import CachedSession

import werkzeug
from werkzeug.security import check_password_hash, generate_password_hash

app: Flask = Flask(__name__)

# Configuring the Flask app
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Setting up caching for APIs to handle rate limits
general_book_cache = CachedSession(
    cache_name='cache/books.db',
    expire_after=timedelta(days=1),
)

book_work_cache = CachedSession(
    cache_name='/cache/book_works.db',
    expire_after=timedelta(days=1),
)

# Establishing a connection to the database
try:
    db: SQL = SQL('sqlite:///bookstore.db')
except RuntimeError:
    # Handles the case where the database doesn't exist (e.g., first-time setup)
    with open('create_table.sql', 'r') as sql_file, open('bookstore.db', 'w') as temp_db:
        db: SQL = SQL('sqlite:///bookstore.db')
        [db.execute(line) for line in sql_file.readlines()]


@app.route('/')
@login_required
def index() -> str:
    """
    Displays the homepage with book recommendations based on the user's last search.

    The function retrieves the top 5 results from the user's last search and displays
    them on the homepage. If no previous search exists, no recommendations are shown.

    Returns:
        str: Rendered HTML template for the homepage.
    """

    def get_urls(books) -> list[str]:
        """
        Retrieves the URLs for the book covers.

        Args:
            books (list[dict]): List of books for cover URLs.

        Returns:
            list[str]: List of URLs for the book covers.
        """
        urls: list[str] = []

        for i in range(5):
            book = books[i]

            # Check if a cover exists for the book. If not, add 'Image not found'.
            if 'cover_edition_key' not in book:
                urls.append('Image not found')
                continue

            # Construct the URL for the book cover
            urls.append(
                f'https://covers.openlibrary.org/b/olid/{book["cover_edition_key"]}-S.jpg'
            )
        return urls

    # Query the user's last search
    last_search = db.execute(
        'SELECT search FROM last_search WHERE user_id=?', session['user_id']
    )

    # If no previous search exists, display an empty homepage
    if len(last_search) < 1:
        return render_template('index.html', books='')

    # Retrieve the top 5 results from the user's last search
    books: dict = general_book_cache.get(last_search[0]['search']).json()['docs']
    return render_template('index.html', books=books, img=get_urls(books))


@app.route('/login', methods=['GET', 'POST'])
def login() -> tuple[str, int] | werkzeug.wrappers.response.Response | str:
    """
    Logs in the user.

    Handles both GET and POST requests. For GET requests, it displays the login page.
    For POST requests, it validates the user's credentials and logs them in.

    Returns:
        tuple[str, int] | werkzeug.wrappers.response.Response | str: Redirects to the homepage
        or displays an error message.
    """
    if request.method == 'GET':
        return render_template('login.html')

    username: str | None = request.form.get('username')
    password: str | None = request.form.get('password')

    if not username:
        return apology('Missing username')

    if not password:
        return apology('Missing password')

    # Retrieve the user's password and ID from the database
    user: list[dict[str, str]] = db.execute(
        'SELECT id, password FROM user WHERE username=?', username
    )

    if len(user) < 1:
        return apology('User does not exist')

    is_password_correct: bool = check_password_hash(user[0]['password'], password)

    if not is_password_correct:
        return apology('Incorrect password')

    # Assign a session cookie to log the user in
    session['user_id'] = user[0]['id']

    return redirect('/')


@app.route('/register', methods=['GET', 'POST'])
def register() -> tuple[str, int] | str | werkzeug.wrappers.response.Response:
    """
    Registers a new user.

    Handles both GET and POST requests. For GET requests, it displays the registration page.
    For POST requests, it validates the input, check if username already exist, and registers
    the user.

    Returns:
        tuple[str, int] | str | werkzeug.wrappers.response.Response: Redirects to the homepage
        or displays an error message.
    """
    session.clear()
    if request.method == 'GET':
        return render_template('register.html')

    username: str | None = request.form.get('username')
    password: str | None = request.form.get('password')

    users: list[dict[str, int | str]] = db.execute('SELECT * FROM user')

    if not username:
        return apology('Missing username')

    # Check if the username is already taken
    for user in users:
        if user['username'] == username:
            return apology('Username taken')

    if not password:
        return apology('Missing password')

    if password != request.form.get('confirm'):
        return apology('Confirmation and password don\'t match')

    # Insert the new user into the database with a hashed password
    db.execute(
        'INSERT INTO user (username, password) VALUES(?,?)',
        username,
        generate_password_hash(password),
    )

    # Assign a session cookie to log the user in
    session['user_id'] = db.execute('SELECT id FROM user WHERE username=?', username)[
        0
    ]['id']

    return redirect('/')


@app.route('/logout')
def logout() -> tuple[str, int] | werkzeug.wrappers.response.Response:
    """
    Logs out the user by clearing their session cookies.

    Returns:
        tuple[str, int] | werkzeug.wrappers.response.Response: Redirects to the login page.
    """
    session.clear()
    return redirect('/login')


@app.route('/search')
@login_required
def search() -> werkzeug.wrappers.response.Response | tuple[str, int] | str:
    """
    Displays search results for books based on the user's query.

    Uses OpenLibrary's search API to fetch and display books based on the user's input.
    Allows sorting in various ways.

    Returns:
        werkzeug.wrappers.response.Response | tuple[str, int] | str: Rendered search results
        or an error message.
    """
    search: str | None = request.args.get('q')
    if not search:
        return apology('Missing search query')

    def get_urls(books: list[dict[str, str | int | float]]) -> list[str]:
        """
        Retrieves URLs for book covers.

        Args:
            books (list[dict]): List of books for cover URLs.

        Returns:
            list[str]: List of URLs for the book covers.
        """
        return [
            (
                f'https://covers.openlibrary.org/b/olid/{book["cover_edition_key"]}-M.jpg'
                if 'cover_edition_key' in book
                else 'Image not found'
            )
            for book in books
        ]

    sort_by: str | None = request.args.get('sort')

    if not sort_by:
        return apology('You cannot sort by nothing')

    # Construct the API URL based on the sort criteria
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

    # Update the user's last search in the database
    db.execute(
        'UPDATE last_search SET search=? WHERE user_id=?', book_url, session['user_id']
    )

    # Check if this is the user's first search
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
    """
    Displays detailed information about a specific book.

    Retrieves the book's description, title, and cover image. Handles cases where
    the user might be coming from the cart or other pages.

    Returns:
        tuple[str, int] | str: Rendered HTML template for the book details page.
    """
    book: str | None = request.form.get('book')
    work: str | None = request.form.get('key')

    # Determine the image format (olid or id)
    if request.form.get('json') != 'True':
        img: str = (
            f'https://covers.openlibrary.org/b/olid/{request.form.get("image")}-L.jpg'
        )
    else:
        img: str = (
            f'https://covers.openlibrary.org/b/olid/{(requests.get(request.form.get("image"))).json()["olid"]}-L.jpg' # type: ignore
        )

    try:
        # Retrieve and clean the book description
        description: str = general_book_cache.get(
            f'https://www.openlibrary.org{work}.json'
        ).json()['description']['value']
        description: str = sub(
            pattern=r'(?:\(\[source\]\[\d+\]\))[^\']*',
            repl='',
            string=description,
            count=0,
            flags=re.MULTILINE,
        )
    except:
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
            description: str = 'No description available.'

    return render_template(
        'details.html', description=description, img=img, id=work, book=book
    )


@app.route('/cart', methods=['GET', 'POST'])
@login_required
def cart() -> tuple[str, int] | str | werkzeug.Response:
    """
    Manages the user's cart.

    Allows users to add books to their cart, view cart items, and return borrowed books.
    Handles both GET and POST requests.

    Returns:
        tuple[str, int] | str | werkzeug.Response: Rendered cart page or redirects.
    """
    is_check_in: bool = True if request.form.get('check-in') == 'True' else False

    if request.method == 'POST' and not is_check_in:
        book_id: str | None = request.form.get('book')

        if not book_id:
            return apology('Missing borrowing book(somehow)')

        # Check if the book is already in the cart
        cart_items: list[dict] = db.execute(
            'SELECT book_id FROM cart WHERE user_id=?', session['user_id']
        )

        if len(cart_items) > 0 and book_id in cart_items[0].values():
            return apology('Book already in cart')

        # Add the book to the cart
        db.execute(
            'INSERT INTO cart (user_id, book_id) VALUES (?, ?)',
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
                'Cart ID missing. If this is not your fault, please try again',
                escape_chars=False,
            )

        # Remove the book from the cart
        db.execute('DELETE FROM cart WHERE cart_id=?', cart_id)

    # Retrieve all items in the user's cart
    cart: list[dict] = db.execute(
        'SELECT * FROM cart WHERE user_id=?', session['user_id']
    )

    # Retrieve cached responses for the books in the cart
    books: list[dict] = [
        book_work_cache.get(
            f'https://www.openlibrary.org/{item["book_id"]}.json'
        ).json()
        for item in cart
    ]

    # Filter out books without covers
    does_cover_exist = lambda cover: cover != -1
    imgs: list[int] = list(
        filter(does_cover_exist, [book['covers'][0] for book in books])
    )

    # Redirect back to the cart page after a POST request
    if request.method == 'POST':
        request.method = 'GET'
        return redirect('/cart')

    return render_template('cart.html', items=cart, books=books, imgs=imgs)


@app.route('/content', methods=['POST'])
@login_required
def content() -> tuple[str, int] | str:
    """
    Displays the content of a book.

    Retrieves the book title from the form data and renders the content page.

    Returns:
        tuple[str, int] | str: Rendered content page or an error message.
    """
    book_title: str | None = request.form.get('book_title')

    if not book_title:
        return apology('Missing book title. Please try again.', escape_chars=False)
    return render_template('content.html', book_title=book_title)


@app.route('/credits')
def credits() -> str:
    """
    Displays the credits page.

    Provides information about the contributors or creators of the website.

    Returns:
        str: Rendered credits page.
    """
    return render_template('credits.html')


@app.route('/license')
def license():
    """
    Displays the license page.

    Reads the license file and renders it for the user to view.

    Returns:
        str: Rendered license page with the license content.
    """
    with open('license', 'r') as f:
        return render_template('license.html', lines=f.readlines())

# End of the project! Thank you for reading all of my code (if you did)!
