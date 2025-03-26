# Online library

### Video Demo:  <https://www.youtube.com/watch?=aaa>

### Note

Ensure your python version is 3.x not 2.x since I don't think an old version of python will work on this program
Also this program isn't very optimized so it might be pretty slow
This took a long time so the styles in the code might be different

### Description

An online website that is basically a library, on which you can borrow various books, view their contents, and read them while staying online.

### How to download and run

1. Ensure you have git installed, if you don't visit this [website](https://git-scm.com/)
2. Clone the repository by downloading it with `git clone https://github.com/me50/PythonDot64/tree/cs50/problems/2022/python/project` or you can download it manually
3. Use `pip install -r requirements.txt` to install the dependicies
4. Then `cd Downloads & tar -xf Bookstore.zip` or something like that in your os
5. Finally run `cd Bookstore & flask run app.py` and click on the url it shows you (I.E: <http://127.0.0.1:5000>)

### Guide

### How to borrow books

First, create an account by clicking the register button. Second search for the desired book in the search bar at the top of the page. Then click the view book button located next to the book title. Finally, click the borrow button to borrow the book.

### How to return books

Click the borrowed books button located at the top of the page, after that you should see the list of books you haved borrowed. Locate the book you want to return and press `Return`. After you confirm that you want to return the book, it should be returned.

### How to view book content

Go to the list of books you haved borrowed, then Locate the book you want to read and press `view book content`. After that you should see the book's content.

### How it works

This program works by using various APIs from Openlibrary: the [search API](https://www.openlibrary.org/dev/docs/api/search) to search for books, the [books API](https://www.openlibrary.org/dev/docs/api/books) for getting info about a paticular book, and the [cover API](https://www.openlibrary.org/dev/docs/api/covers) for getting the cover of a. The program also uses a lot of libraries such as re for removing unwanted text, cs50 for the SQLite3 database and flask for the server side of the website

### Credits

[Openlibrary](https://www.openlibrary.org) for [their amazing APIs](https://www.openlibrary.org/dev/docs/api) (Application Programming Interface) for searching books. This project would not have been possible without their APIs.
