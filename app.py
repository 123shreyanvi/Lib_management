import gradio as gr
import json
import threading


class BookNotFoundError(Exception): pass
class AlreadyBorrowedError(Exception): pass
class DatabaseError(Exception): pass
class MemberNotFoundError(Exception): pass

class Book:
    def __init__(self, book_id, title, author, total_copies=1, available_copies=None):
        self.book_id = book_id
        self.title = title
        self.author = author
        self.total_copies = total_copies
        self.available_copies = available_copies if available_copies is not None else total_copies
    
    def __str__(self):
        return f"[{self.book_id}] {self.title} by {self.author} - {self.available_copies}/{self.total_copies} Available"
    
    def to_dict(self):
        return {
            "book_id": self.book_id,
            "title": self.title,
            "author": self.author,
            "total_copies": self.total_copies,
            "available_copies": self.available_copies
        }

    @staticmethod
    def from_dict(data):
        return Book(
            data["book_id"], 
            data["title"], 
            data["author"], 
            data.get("total_copies", 1), 
            data.get("available_copies", data.get("total_copies", 1))
        )

# --- Member Class ---
class Member:
    def __init__(self, member_id, name, borrowed_books=None):
        self.member_id = member_id
        self.name = name
        self.borrowed_books = borrowed_books if borrowed_books else []
    
    def borrow_book(self, book):
        if book.available_copies <= 0:
            raise AlreadyBorrowedError(f"No copies of '{book.title}' available right now.")
        book.available_copies -= 1
        self.borrowed_books.append(book.book_id)
    
    def return_book(self, book):
        if book.book_id in self.borrowed_books:
            book.available_copies = min(book.available_copies + 1, book.total_copies)
            self.borrowed_books.remove(book.book_id)
    
    def __str__(self):
        return f"Member[{self.member_id}] {self.name} - Borrowed: {self.borrowed_books}"
    
    def to_dict(self):
        return {
            "member_id": self.member_id,
            "name": self.name,
            "borrowed_books": self.borrowed_books
        }
    
    @staticmethod
    def from_dict(data):
        return Member(data["member_id"], data["name"], data["borrowed_books"])

# --- Library Class ---
class Library:
    def __init__(self, books_file="library_books.json", members_file="library_members.json",
                 available_file="available_books.json", borrowed_file="borrowed_books.json"):
        self.books = []   # store Book objects
        self.members = {} # store Member objects
        self.lock = threading.Lock()
        
        self.books_file = books_file
        self.members_file = members_file
        self.available_file = available_file
        self.borrowed_file = borrowed_file

        self.load_from_file()
    
    def add_member(self, member):
        self.members[member.member_id] = member
        self.save_to_file()
    
    def get_member(self, member_id):
        if member_id not in self.members:
            raise MemberNotFoundError(f"Member ID {member_id} not found.")
        return self.members[member_id]
    
    def add_book(self, book):
        self.books.append(book)
        self.save_to_file()
    
    def search_book(self, title):
        for book in self.books:
            if book.title.lower() == title.lower():
                return book
        raise BookNotFoundError(f"{title} not found.")
    
    def borrow_book(self, member_id, title):
        with self.lock:
            member = self.get_member(member_id)
            book = self.search_book(title)
            member.borrow_book(book)
            self.save_to_file()
    
    def return_book(self, member_id, title):
        with self.lock:
            member = self.get_member(member_id)
            book = self.search_book(title)
            member.return_book(book)
            self.save_to_file()
    
    def save_to_file(self):
        try:
            with open(self.books_file, "w") as f:
                json.dump([book.to_dict() for book in self.books], f, indent=4)
            with open(self.members_file, "w") as f:
                json.dump([member.to_dict() for member in self.members.values()], f, indent=4)
            with open(self.available_file, "w") as f:
                json.dump([book.to_dict() for book in self.books if book.available_copies > 0], f, indent=4)
            with open(self.borrowed_file, "w") as f:
                json.dump([book.to_dict() for book in self.books if book.available_copies < book.total_copies], f, indent=4)
        except Exception as e:
            raise DatabaseError("Save failed: " + str(e))
    
    def load_from_file(self):
        try:
            with open(self.books_file, "r") as f:
                data = json.load(f)
                self.books = [Book.from_dict(book) for book in data]
        except FileNotFoundError:
            self.books = []
        
        try:
            with open(self.members_file, "r") as f:
                data = json.load(f)
                self.members = {m["member_id"]: Member.from_dict(m) for m in data}
        except FileNotFoundError:
            self.members = {}

# --- Gradio Interface ---
lib = Library()

def add_book(book_id, title, author, copies):
    try:
        b = Book(int(book_id), title, author, int(copies))
        lib.add_book(b)
        return "✅ Book added successfully."
    except Exception as e:
        return f"❌ Error: {e}"

def add_member(member_id, name):
    try:
        m = Member(int(member_id), name)
        lib.add_member(m)
        return "✅ Member added successfully."
    except Exception as e:
        return f"❌ Error: {e}"

def borrow_book(member_id, title):
    try:
        lib.borrow_book(int(member_id), title)
        return "✅ Book borrowed successfully."
    except Exception as e:
        return f"❌ Error: {e}"

def return_book(member_id, title):
    try:
        lib.return_book(int(member_id), title)
        return "✅ Book returned successfully."
    except Exception as e:
        return f"❌ Error: {e}"

def show_all_books():
    if not lib.books:
        return "📚 No books available."
    return "\n".join([str(b) for b in lib.books])

def show_all_members():
    if not lib.members:
        return "👤 No members available."
    return "\n".join([str(m) for m in lib.members.values()])

def show_available_books():
    return "\n".join([str(b) for b in lib.books if b.available_copies > 0]) or "No available books."

def show_borrowed_books():
    return "\n".join([str(b) for b in lib.books if b.available_copies < b.total_copies]) or "No borrowed books."

with gr.Blocks() as demo:
    gr.Markdown("# 📚 Library Management System ")

    with gr.Tab("Add Book"):
        book_id = gr.Number(label="Book ID")
        title = gr.Textbox(label="Title")
        author = gr.Textbox(label="Author")
        copies = gr.Number(label="Copies", value=1)
        out1 = gr.Textbox(label="Result")
        btn1 = gr.Button("Add Book")
        btn1.click(add_book, [book_id, title, author, copies], out1)

    with gr.Tab("Add Member"):
        member_id = gr.Number(label="Member ID")
        name = gr.Textbox(label="Name")
        out2 = gr.Textbox(label="Result")
        btn2 = gr.Button("Add Member")
        btn2.click(add_member, [member_id, name], out2)

    with gr.Tab("Borrow/Return"):
        mem_id = gr.Number(label="Member ID")
        book_title = gr.Textbox(label="Book Title")
        out3 = gr.Textbox(label="Result")
        btn3 = gr.Button("Borrow Book")
        btn4 = gr.Button("Return Book")
        btn3.click(borrow_book, [mem_id, book_title], out3)
        btn4.click(return_book, [mem_id, book_title], out3)

    with gr.Tab("Show Data"):
        out4 = gr.Textbox(label="All Books", lines=10)
        out5 = gr.Textbox(label="All Members", lines=10)
        out6 = gr.Textbox(label="Available Books", lines=10)
        out7 = gr.Textbox(label="Borrowed Books", lines=10)

        btn5 = gr.Button("Show All Books")
        btn6 = gr.Button("Show All Members")
        btn7 = gr.Button("Show Available Books")
        btn8 = gr.Button("Show Borrowed Books")

        btn5.click(show_all_books, outputs=out4)
        btn6.click(show_all_members, outputs=out5)
        btn7.click(show_available_books, outputs=out6)
        btn8.click(show_borrowed_books, outputs=out7)
demo.launch()
