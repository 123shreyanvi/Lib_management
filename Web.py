import tkinter as tk
from tkinter import simpledialog, messagebox, scrolledtext
import json, os
from datetime import datetime, timedelta

DATA_FILE = "library_data.json"
DATE_FMT = "%Y-%m-%d %H:%M"

# -------------------------------
# Models
# -------------------------------
class Book:
    def __init__(self, book_id, title, author, is_borrowed=False, borrower_id=None, due_date=None):
        self.book_id = str(book_id)
        self.title = title
        self.author = author
        self.is_borrowed = is_borrowed
        self.borrower_id = borrower_id
        self.due_date = due_date  

    def to_dict(self):
        return {
            "book_id": self.book_id,
            "title": self.title,
            "author": self.author,
            "is_borrowed": self.is_borrowed,
            "borrower_id": self.borrower_id,
            "due_date": self.due_date,
        }

    def __str__(self):
        status = "Available"
        extra = ""
        if self.is_borrowed:
            status = "Borrowed"
            who = self.borrower_id if self.borrower_id else "N/A"
            dd = self.due_date if self.due_date else "N/A"
            extra = f" | Borrower: {who} | Due: {dd}"
        return f"[{self.book_id}] {self.title} — {self.author}  ({status}){extra}"


class Member:
    def __init__(self, member_id, name, borrowed_book_ids=None):
        self.member_id = str(member_id)
        self.name = name
        self.borrowed_book_ids = borrowed_book_ids or []

    def to_dict(self):
        return {
            "member_id": self.member_id,
            "name": self.name,
            "borrowed_book_ids": self.borrowed_book_ids,
        }

    def __str__(self):
        return f"[{self.member_id}] {self.name} | Borrowed: {len(self.borrowed_book_ids)}"


# -------------------------------
# Library (backend)
# -------------------------------
class Library:
    def __init__(self):
        self.books = {}    # id -> Book
        self.members = {}  # id -> Member
        self.history = []  # list of dicts (timestamp, action, book_id, member_id, fine)
        self.load_data()

    # ---------- Persistence ----------
    def save_data(self):
        data = {
            "books": {bid: b.to_dict() for bid, b in self.books.items()},
            "members": {mid: m.to_dict() for mid, m in self.members.items()},
            "history": self.history,
        }
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_data(self):
        """Load data from JSON file, or start fresh if file is empty/corrupt"""
        try:
            if os.path.exists("library_data.json"):
                with open("library_data.json", "r") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    data = {"books": {}, "members": {}, "history": []}

                self.books = {bid: Book(**bdict) for bid, bdict in data.get("books", {}).items()}
                self.members = {mid: Member(**mdict) for mid, mdict in data.get("members", {}).items()}
                self.history = data.get("history", [])
            else:
                self.books, self.members, self.history = {}, {}, []
        except Exception as e:
            print("Error loading data, starting fresh:", e)
            self.books, self.members, self.history = {}, {}, []

    # ---------- Helpers ----------
    def _now(self):
        return datetime.now().strftime(DATE_FMT)

    def _find_book_by_title_ci(self, title):
        title = (title or "").strip().lower()
        for b in self.books.values():
            if b.title.lower() == title:
                return b
        return None

    def _find_member_by_name_ci(self, name):
        name = (name or "").strip().lower()
        for m in self.members.values():
            if m.name.lower() == name:
                return m
        return None

    # ---------- Core Ops ----------
    def add_book(self, book_id, title, author):
        if str(book_id) in self.books:
            return False, "Book ID already exists."
        self.books[str(book_id)] = Book(str(book_id), title.strip(), author.strip())
        self.save_data()
        return True, "Book added."

    def add_member(self, member_id, name):
        if str(member_id) in self.members:
            return False, "Member ID already exists."
        self.members[str(member_id)] = Member(str(member_id), name.strip())
        self.save_data()
        return True, "Member added."

    def borrow_book(self, member_key, book_key, by_title=False, by_name=False):
        m = self._find_member_by_name_ci(member_key) if by_name else self.members.get(str(member_key))
        if not m:
            return False, "Member not found."

        b = self._find_book_by_title_ci(book_key) if by_title else self.books.get(str(book_key))
        if not b:
            return False, "Book not found."

        if b.is_borrowed:
            return False, "Book already borrowed."

        b.is_borrowed = True
        b.borrower_id = m.member_id
        b.due_date = (datetime.now() + timedelta(days=7)).strftime(DATE_FMT)
        m.borrowed_book_ids.append(b.book_id)

        self.history.append({
            "timestamp": self._now(),
            "action": "borrow",
            "book_id": b.book_id,
            "member_id": m.member_id,
            "due_date": b.due_date,
        })
        self.save_data()
        return True, f"{m.name} borrowed '{b.title}'. Due: {b.due_date}"

    def return_book(self, member_key, book_key, by_title=False, by_name=False):
        m = self._find_member_by_name_ci(member_key) if by_name else self.members.get(str(member_key))
        if not m:
            return False, "Member not found."

        b = self._find_book_by_title_ci(book_key) if by_title else self.books.get(str(book_key))
        if not b:
            return False, "Book not found."

        if not b.is_borrowed or b.borrower_id != m.member_id:
            return False, "This member does not hold that book."

        # Fine calculation
        fine = 0
        if b.due_date:
            try:
                due = datetime.strptime(b.due_date, DATE_FMT)
                late_days = (datetime.now() - due).days
                if late_days > 0:
                    fine = late_days * 10
            except Exception:
                fine = 0
        b.is_borrowed = False
        b.borrower_id = None
        b.due_date = None
        if b.book_id in m.borrowed_book_ids:
            m.borrowed_book_ids.remove(b.book_id)

        self.history.append({
            "timestamp": self._now(),
            "action": "return",
            "book_id": b.book_id,
            "member_id": m.member_id,
            "fine": fine,
        })
        self.save_data()

        msg = f"Returned '{b.title}'."
        if fine > 0:
            msg += f" Late fine: ₹{fine}"
        return True, msg

    def search_books(self, keyword):
        kw = (keyword or "").strip().lower()
        results = []
        for b in self.books.values():
            if kw in b.title.lower() or kw in b.author.lower():
                results.append(b)
        return results

# -------------------------------
# GUI
# -------------------------------
class LibraryApp:
    def __init__(self, root):
        self.lib = Library()
        self.root = root
        self.root.title("📚 Library Management System")
        self.root.geometry("840x560")
        self.root.configure(bg="#f5f7fb")
        tk.Label(
            root, text="📚 Library Management System",
            font=("Segoe UI", 20, "bold"), bg="#3b82f6", fg="white", pady=10
        ).pack(fill="x")
        body = tk.Frame(root, bg="#f5f7fb")
        body.pack(fill="both", expand=True, padx=12, pady=12)

        left = tk.Frame(body, bg="#f5f7fb")
        left.pack(side="left", fill="y")
        right = tk.Frame(body, bg="#f5f7fb")
        right.pack(side="right", fill="both", expand=True)
        def add_btn(text, cmd, bg="#3b82f6"):
            tk.Button(
                left, text=text, command=cmd, width=22, height=2,
                font=("Segoe UI", 11, "bold"), bg=bg, fg="white", bd=0, activebackground="#2563eb"
            ).pack(pady=6, anchor="w")

        add_btn("➕ Add Book", self.ui_add_book, "#10b981")
        add_btn("👤 Add Member", self.ui_add_member, "#10b981")
        add_btn("📥 Borrow (by IDs)", self.ui_borrow_by_ids, "#3b82f6")
        add_btn("📥 Borrow (Name/Title)", self.ui_borrow_by_names, "#3b82f6")
        add_btn("📤 Return (by IDs)", self.ui_return_by_ids, "#3b82f6")
        add_btn("📤 Return (Name/Title)", self.ui_return_by_names, "#3b82f6")
        add_btn("🔎 Search Books", self.ui_search, "#8b5cf6")
        add_btn("📚 Show All Books", self.ui_show_books, "#64748b")
        add_btn("🧑 Show All Members", self.ui_show_members, "#64748b")
        add_btn("🕓 Show History", self.ui_show_history, "#64748b")
        add_btn("❌ Exit", self.ui_exit, "#ef4444")
        tk.Label(right, text="📌 Output", font=("Segoe UI", 13, "bold"), bg="#f5f7fb").pack(anchor="w")
        self.output = scrolledtext.ScrolledText(
            right, height=24, font=("Consolas", 11)
        )
        self.output.pack(fill="both", expand=True, pady=(6, 0))

        self.ui_show_books()

    # ---------------- UI Helpers ----------------
    def write_lines(self, lines):
        self.output.delete(1.0, tk.END)
        if isinstance(lines, str):
            self.output.insert(tk.END, lines + "\n")
        else:
            for line in lines:
                self.output.insert(tk.END, str(line) + "\n")

    def ask(self, title, prompt):
        return simpledialog.askstring(title, prompt, parent=self.root)

    # ---------------- UI Actions ----------------
    def ui_add_book(self):
        bid = self.ask("Add Book", "Enter Book ID:")
        title = self.ask("Add Book", "Enter Title:")
        author = self.ask("Add Book", "Enter Author:")
        if not (bid and title and author):
            return
        ok, msg = self.lib.add_book(bid.strip(), title.strip(), author.strip())
        messagebox.showinfo("Add Book", msg)
        self.ui_show_books()

    def ui_add_member(self):
        mid = self.ask("Add Member", "Enter Member ID:")
        name = self.ask("Add Member", "Enter Member Name:")
        if not (mid and name):
            return
        ok, msg = self.lib.add_member(mid.strip(), name.strip())
        messagebox.showinfo("Add Member", msg)
        self.ui_show_members()

    def ui_borrow_by_ids(self):
        mid = self.ask("Borrow Book", "Member ID:")
        bid = self.ask("Borrow Book", "Book ID:")
        if not (mid and bid): return
        ok, msg = self.lib.borrow_book(mid.strip(), bid.strip(), by_title=False, by_name=False)
        messagebox.showinfo("Borrow", msg if ok else f"Failed: {msg}")
        self.ui_show_books()

    def ui_borrow_by_names(self):
        mname = self.ask("Borrow Book", "Member Name:")
        title = self.ask("Borrow Book", "Book Title:")
        if not (mname and title): return
        ok, msg = self.lib.borrow_book(mname.strip(), title.strip(), by_title=True, by_name=True)
        messagebox.showinfo("Borrow", msg if ok else f"Failed: {msg}")
        self.ui_show_books()

    def ui_return_by_ids(self):
        mid = self.ask("Return Book", "Member ID:")
        bid = self.ask("Return Book", "Book ID:")
        if not (mid and bid): return
        ok, msg = self.lib.return_book(mid.strip(), bid.strip(), by_title=False, by_name=False)
        messagebox.showinfo("Return", msg if ok else f"Failed: {msg}")
        self.ui_show_books()

    def ui_return_by_names(self):
        mname = self.ask("Return Book", "Member Name:")
        title = self.ask("Return Book", "Book Title:")
        if not (mname and title): return
        ok, msg = self.lib.return_book(mname.strip(), title.strip(), by_title=True, by_name=True)
        messagebox.showinfo("Return", msg if ok else f"Failed: {msg}")
        self.ui_show_books()

    def ui_search(self):
        kw = self.ask("Search", "Enter title/author keyword:")
        if kw is None: return
        results = self.lib.search_books(kw)
        self.write_lines(results if results else ["No matching books found."])

    def ui_show_books(self):
        if not self.lib.books:
            self.write_lines("No books in library yet.")
            return
        # Sort by title for nice display
        lines = [self.lib.books[k] for k in sorted(self.lib.books, key=lambda x: self.lib.books[x].title.lower())]
        self.write_lines(lines)

    def ui_show_members(self):
        if not self.lib.members:
            self.write_lines("No members yet.")
            return
        lines = [self.lib.members[k] for k in sorted(self.lib.members, key=lambda x: self.lib.members[x].name.lower())]
        self.write_lines(lines)

    def ui_show_history(self):
        if not self.lib.history:
            self.write_lines("No transactions yet.")
            return
        lines = []
        for h in self.lib.history[::-1]:
            if h["action"] == "borrow":
                lines.append(f"{h['timestamp']} | BORROW | Book {h['book_id']} | Member {h['member_id']} | Due {h.get('due_date','')}")
            else:
                lines.append(f"{h['timestamp']} | RETURN | Book {h['book_id']} | Member {h['member_id']} | Fine ₹{h.get('fine',0)}")
        self.write_lines(lines)

    def ui_exit(self):
        if messagebox.askyesno("Exit", "Do you really want to exit?"):
            self.lib.save_data()
            self.root.destroy()

# -------------------------------
# Main
# -------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = LibraryApp(root)
    root.mainloop()
