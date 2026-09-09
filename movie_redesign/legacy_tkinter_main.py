import hashlib
import random
import re
import smtplib
import textwrap
import tkinter as tk
from email.message import EmailMessage
from tkinter import messagebox, ttk

import mysql.connector


# ------------------------- SETTINGS -------------------------
# Change these values before running the project.
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = "srinath"       # Put your MySQL password here if neededD
DB_NAME = "movie_booking_db"

EMAIL_ADDRESS = "srinaath25@gmail.com"
EMAIL_APP_PASSWORD = "come znel zwlk eqnc"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

ADMIN_EMAIL = "admin@movie.com"
ADMIN_PASSWORD = "admin123"


# ------------------------- STANDARDIZED MOVIE ENUMS --------
MOVIE_CATEGORIES = [
    "Action", "Drama", "Comedy", "Thriller", "Sci-Fi",
    "Romance", "Animation", "Horror", "Adventure", "Fantasy",
    "Crime", "Other"
]

MOVIE_DATE_STATUSES = [
    "Now Showing",
    "Pre-booking",
    "Releasing Soon",
    "Ended"
]

MOVIE_BADGES = [
    "None",
    "Trending",
    "Blockbuster Run",
    "Critic's Choice",
    "Housefull"
]

BADGE_CONFIG = {
    "Trending": {"bg": "#dc2626", "fg": "white", "icon": "🔥", "label": "TRENDING"},
    "Blockbuster Run": {"bg": "#7c3aed", "fg": "white", "icon": "🏆", "label": "BLOCKBUSTER RUN"},
    "Critic's Choice": {"bg": "#d97706", "fg": "white", "icon": "⭐", "label": "CRITIC'S CHOICE"},
    "Housefull": {"bg": "#be123c", "fg": "white", "icon": "🎟️", "label": "HOUSEFULL"},
}


# ------------------------- COLORS ---------------------------
BG = "#eef4f8"
PANEL = "#ffffff"
TEXT = "#1f2937"
MUTED = "#6b7280"
BLUE = "#2563eb"
BLUE_DARK = "#1d4ed8"
GREEN = "#16a34a"
RED = "#dc2626"
RED_DARK = "#b91c1c"
ORANGE = "#f97316"
GREY = "#e5e7eb"
YELLOW = "#fff7cc"


# ------------------------- DATABASE -------------------------
def password_hash(password):
    return hashlib.sha256(password.encode()).hexdigest()


def connect_server():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD
    )


def connect_db():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )


def fetch_all(query, values=()):
    db = connect_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(query, values)
    rows = cursor.fetchall()
    cursor.close()
    db.close()
    return rows


def fetch_one(query, values=()):
    db = connect_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(query, values)
    row = cursor.fetchone()
    cursor.close()
    db.close()
    return row


def run_query(query, values=()):
    db = connect_db()
    cursor = db.cursor()
    cursor.execute(query, values)
    db.commit()
    new_id = cursor.lastrowid
    cursor.close()
    db.close()
    return new_id


def is_valid_email(email):
    """Validate email format using regex pattern."""
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))


def setup_database():
    server = connect_server()
    cursor = server.cursor()
    cursor.execute("CREATE DATABASE IF NOT EXISTS " + DB_NAME)
    server.commit()
    cursor.close()
    server.close()

    db = connect_db()
    cursor = db.cursor()

    # Execute schema setup from database.sql if present
    try:
        with open("database.sql", "r", encoding="utf-8") as f:
            sql_commands = f.read().split(";")
            for cmd in sql_commands:
                stmt = cmd.strip()
                if stmt:
                    cursor.execute(stmt)
        db.commit()
    except FileNotFoundError:
        pass

    # Ensure bypass column exists on users table
    try:
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'users' AND column_name = 'bypass'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("ALTER TABLE users ADD COLUMN bypass BOOLEAN DEFAULT FALSE")
            db.commit()
    except Exception:
        pass

    # Ensure badge column exists on movies table
    try:
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'movies' AND column_name = 'badge'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("ALTER TABLE movies ADD COLUMN badge VARCHAR(50) DEFAULT 'None'")
            db.commit()
    except Exception:
        pass

    # Ensure no stale held seats linger from crashed/closed previous sessions
    try:
        cursor.execute("UPDATE seats SET status='free', booked_by=NULL WHERE status='held'")
        db.commit()
    except Exception:
        pass

    seed_data(cursor, db)
    cursor.close()
    db.close()


def seed_data(cursor, db):
    """
    Seed data function - currently empty.
    All initial data should be added through the Admin Panel UI.

    Note: When shows are created via admin panel, seats will need to be
    generated automatically (6 rows A-F, 8 seats per row = 48 seats per show).
    """
    # Ensure seats exist for any shows that were added
    cursor.execute("SELECT id FROM shows")
    show_ids = [row[0] for row in cursor.fetchall()]

    for show_id in show_ids:
        # Check if seats already exist for this show
        cursor.execute("SELECT COUNT(*) FROM seats WHERE show_id=%s", (show_id,))
        seat_count = cursor.fetchone()[0]

        if seat_count == 0:
            # Generate 48 seats (A-F rows, 1-8 columns)
            for letter in "ABCDEF":
                for number in range(1, 9):
                    seat_no = letter + str(number)
                    cursor.execute("""
                        INSERT IGNORE INTO seats (show_id, seat_no, status)
                        VALUES (%s,%s,'free')
                    """, (show_id, seat_no))

    db.commit()


# ------------------------- EMAIL ----------------------------
def send_email(to_email, subject, body):
    if EMAIL_ADDRESS == "your_email@gmail.com":
        print("\nEMAIL DEMO MODE")
        print("To:", to_email)
        print("Subject:", subject)
        print(body)
        print("Add your email settings in main.py to send real email.\n")
        return True

    message = EmailMessage()
    message["From"] = EMAIL_ADDRESS
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        server.send_message(message)
        server.quit()
        return True
    except Exception as error:
        messagebox.showerror("Email Error", "Could not send email:\n" + str(error))
        return False


def make_otp():
    return str(random.randint(100000, 999999))


# ------------------------- UI HELPERS -----------------------
def label(parent, text, size=12, color=TEXT, bold=False):
    font = ("Segoe UI", size, "bold" if bold else "normal")
    return tk.Label(parent, text=text, font=font, bg=parent["bg"], fg=color)


def wrapped_label(parent, text, size=12, color=TEXT, bold=False, wraplength=400):
    font = ("Segoe UI", size, "bold" if bold else "normal")
    return tk.Label(
        parent, text=text, font=font, bg=parent["bg"], fg=color,
        wraplength=wraplength, justify="left"
    )


def entry(parent, show=None):
    box = tk.Entry(
        parent, font=("Segoe UI", 12), bd=0, relief="flat",
        bg="#f8fafc", fg=TEXT, show=show, insertbackground=TEXT
    )
    box.configure(highlightbackground="#d1d5db", highlightthickness=1)
    return box


def dropdown(parent, values, default=None, width=None):
    cb = ttk.Combobox(
        parent, values=values, state="readonly",
        font=("Segoe UI", 11), width=width
    )
    if default and default in values:
        cb.set(default)
    elif values:
        cb.set(values[0])
    return cb


def render_badge(parent, badge_value, size=9, pady=(0, 6)):
    if not badge_value or str(badge_value).strip() in ("None", "", "none"):
        return None
    b_key = str(badge_value).strip()
    cfg = BADGE_CONFIG.get(b_key, {"bg": BLUE, "fg": "white", "icon": "🏷️", "label": b_key.upper()})
    frame = tk.Frame(parent, bg=cfg["bg"], padx=8, pady=2)
    frame.pack(anchor="w", pady=pady)
    text = f"{cfg['icon']} {cfg['label']}"
    tk.Label(
        frame, text=text, bg=cfg["bg"], fg=cfg["fg"],
        font=("Segoe UI", size, "bold")
    ).pack()
    return frame


def button(parent, text, command, color=BLUE):
    active_map = {BLUE: BLUE_DARK, GREEN: "#15803d", RED: RED_DARK,
                  ORANGE: "#ea580c", MUTED: "#4b5563"}
    active_bg = active_map.get(color, color)
    btn = tk.Button(
        parent, text=text, command=command, bg=color, fg="white",
        activebackground=active_bg, activeforeground="white",
        font=("Segoe UI", 11, "bold"), bd=0, padx=16, pady=9,
        cursor="hand2"
    )
    return btn


def card(parent):
    frame = tk.Frame(parent, bg=PANEL, bd=0, highlightthickness=1,
                     highlightbackground="#dbe4ea")
    return frame


class ScrollableFrame(tk.Frame):
    """
    A smooth, reusable scrollable frame container with vertical scrollbar
    and universal mousewheel support on Windows.
    """
    _active_frames = []
    _global_wheel_bound = False

    def __init__(self, parent, bg=BG, **kwargs):
        super().__init__(parent, bg=bg, **kwargs)
        ScrollableFrame._active_frames.append(self)

        self.canvas = tk.Canvas(self, bg=bg, bd=0, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_content = tk.Frame(self.canvas, bg=bg)

        self.scrollable_content.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_content, anchor="nw")

        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width)
        )

        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self._bind_wheel_events()

    def _bind_wheel_events(self):
        if not ScrollableFrame._global_wheel_bound:
            try:
                top = self.winfo_toplevel()
                top.bind_all("<MouseWheel>", ScrollableFrame._on_global_mousewheel, add="+")
                ScrollableFrame._global_wheel_bound = True
            except Exception:
                pass

    @classmethod
    def _on_global_mousewheel(cls, event):
        cls._active_frames = [f for f in cls._active_frames if f.winfo_exists()]
        if not cls._active_frames:
            return

        try:
            x, y = event.x_root, event.y_root
            for frame in reversed(cls._active_frames):
                if not frame.winfo_exists():
                    continue
                fx = frame.winfo_rootx()
                fy = frame.winfo_rooty()
                fw = frame.winfo_width()
                fh = frame.winfo_height()
                if fx <= x <= fx + fw and fy <= y <= fy + fh:
                    delta = int(-1 * (event.delta / 120)) * 2
                    frame.canvas.yview_scroll(delta, "units")
                    return
        except Exception:
            pass

    def destroy(self):
        if self in ScrollableFrame._active_frames:
            ScrollableFrame._active_frames.remove(self)
        super().destroy()


# ------------------------- APPLICATION ----------------------
class MovieBookingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Movie Booking Service")
        self.root.geometry("1100x720")
        self.root.minsize(1000, 650)
        self.root.configure(bg=BG, cursor="hand2")

        self.current_page = None
        self.current_user = None
        self.login_otp = ""
        self.payment_otp = ""
        self.selected_movie = None
        self.selected_show = None
        self.selected_seats = []
        self.selected_snacks = {}

        self.container = tk.Frame(root, bg=BG)
        self.container.pack(fill="both", expand=True)

        self.root.protocol("WM_DELETE_WINDOW", self.on_app_close)

        self.show_start()

    def on_app_close(self):
        self.release_held_seats()
        self.root.destroy()

    def release_held_seats(self):
        if self.current_user and self.selected_show and self.selected_seats:
            try:
                placeholders = ",".join(["%s"] * len(self.selected_seats))
                run_query(
                    f"UPDATE seats SET status='free', booked_by=NULL "
                    f"WHERE show_id=%s AND seat_no IN ({placeholders}) AND status='held' AND booked_by=%s",
                    tuple([self.selected_show["id"]] + self.selected_seats + [self.current_user["id"]])
                )
            except Exception:
                pass
        self.selected_seats = []

    def clear_page(self):
        if self.current_page:
            self.current_page.destroy()

    def switch_page(self, build_function):
        old_page = self.current_page
        new_page = tk.Frame(self.container, bg=BG)
        self.current_page = new_page

        self.root.update_idletasks()
        width = self.container.winfo_width()
        if width < 100:
            width = 1100

        new_page.place(x=width, y=0, relwidth=1, relheight=1)
        build_function(new_page)

        blur = tk.Frame(self.container, bg="#b7d4ff")
        blur.place(x=width - 45, y=0, width=45, relheight=1)
        self.root.configure(cursor="watch")

        steps = 18

        def animate(step):
            if step <= steps:
                x = int(width - (width * step / steps))
                new_page.place(x=x, y=0, relwidth=1, relheight=1)
                blur.place(x=max(x - 35, 0), y=0, width=45, relheight=1)
                if old_page:
                    old_page.place(x=int(-120 * step / steps), y=0, relwidth=1, relheight=1)
                self.root.after(12, lambda: animate(step + 1))
            else:
                new_page.place(x=0, y=0, relwidth=1, relheight=1)
                blur.destroy()
                if old_page:
                    old_page.destroy()
                self.root.configure(cursor="hand2")

        animate(0)

    def show_start(self):
        self.release_held_seats()
        self.switch_page(self.build_start)

    def build_start(self, page):
        page.configure(bg=BG)

        header = tk.Frame(page, bg=BG)
        header.pack(fill="x", padx=45, pady=(32, 15))
        label(header, "Movie Booking Service", 30, TEXT, True).pack(anchor="w")
        label(header, "Book tickets, select seats, buy snacks and receive OTP/tickets on email.",
              13, MUTED).pack(anchor="w", pady=(5, 0))

        center = tk.Frame(page, bg=BG)
        center.pack(expand=True, pady=20)

        # User Portal Section
        user_card = card(center)
        user_card.grid(row=0, column=0, padx=25, ipadx=40, ipady=40, sticky="n")

        # User icon/badge
        user_badge = tk.Label(user_card, text="👤", font=("Segoe UI", 32), bg=PANEL)
        user_badge.pack(pady=(0, 10))

        label(user_card, "User Portal", 24, TEXT, True).pack(pady=(0, 5))
        label(user_card, "Book tickets, choose seats, order snacks", 11, MUTED).pack(pady=(0, 20))

        button(user_card, "Sign In", lambda: self.show_user_login(), BLUE).pack(fill="x", pady=5)
        button(user_card, "Create New Account", self.show_register, GREEN).pack(fill="x", pady=5)

        label(user_card, "Secure OTP verification via email", 9, MUTED).pack(pady=(15, 0))
        label(user_card, "Test User: test@movie.com / test123 (No OTP)", 9, GREEN).pack(pady=(3, 0))

        # Admin Portal Section
        admin_card = card(center)
        admin_card.grid(row=0, column=1, padx=25, ipadx=40, ipady=40, sticky="n")

        # Admin icon/badge
        admin_badge = tk.Label(admin_card, text="🔐", font=("Segoe UI", 32), bg=PANEL)
        admin_badge.pack(pady=(0, 10))

        label(admin_card, "Admin Portal", 24, TEXT, True).pack(pady=(0, 5))
        label(admin_card, "Manage movies, dates, offers & bookings", 11, MUTED).pack(pady=(0, 20))

        button(admin_card, "Administrator Sign In", lambda: self.show_admin_login(), ORANGE).pack(fill="x", pady=5)

        label(admin_card, "Restricted access for cinema staff", 9, MUTED).pack(pady=(15, 0))
        label(admin_card, "Default: admin@movie.com / admin123", 9, MUTED).pack(pady=(3, 0))

        bottom = tk.Frame(page, bg=BG)
        bottom.pack(fill="x", padx=45, pady=28)
        for text in ["Trends", "Upcoming", "Long Bored", "Seat Plan", "Snacks", "Email OTP"]:
            chip = tk.Label(bottom, text=text, bg="#dbeafe", fg="#1e3a8a",
                            font=("Segoe UI", 10, "bold"), padx=14, pady=7)
            chip.pack(side="left", padx=6)

    def show_register(self):
        self.switch_page(self.build_register)

    def show_user_login(self):
        self.switch_page(self.build_user_login)

    def show_admin_login(self):
        self.switch_page(self.build_admin_login)

    def build_register(self, page):
        form = card(page)
        form.pack(expand=True, ipadx=45, ipady=35)

        label(form, "Create Account", 24, TEXT, True).grid(row=0, column=0, columnspan=2, pady=(0, 5))
        label(form, "Enter your details to register as a new user", 11, MUTED).grid(row=1, column=0, columnspan=2, pady=(0, 20))

        label(form, "Full Name").grid(row=2, column=0, sticky="e", padx=(0, 10), pady=6)
        name_box = entry(form)
        name_box.grid(row=2, column=1, sticky="ew", pady=6, ipady=7)

        label(form, "Email Address").grid(row=3, column=0, sticky="e", padx=(0, 10), pady=6)
        email_box = entry(form)
        email_box.grid(row=3, column=1, sticky="ew", pady=6, ipady=7)

        label(form, "Password").grid(row=4, column=0, sticky="e", padx=(0, 10), pady=6)
        pass_box = entry(form, show="*")
        pass_box.grid(row=4, column=1, sticky="ew", pady=6, ipady=7)

        label(form, "Confirm Password").grid(row=5, column=0, sticky="e", padx=(0, 10), pady=6)
        confirm_pass_box = entry(form, show="*")
        confirm_pass_box.grid(row=5, column=1, sticky="ew", pady=6, ipady=7)

        form.grid_columnconfigure(1, weight=1)

        def save_user():
            name = name_box.get().strip()
            email = email_box.get().strip().lower()
            password = pass_box.get().strip()
            confirm_password = confirm_pass_box.get().strip()

            # Validation: Blank fields check
            if not name:
                messagebox.showwarning("Missing Name", "Please enter your full name.")
                name_box.focus()
                return
            if not email:
                messagebox.showwarning("Missing Email", "Please enter your email address.")
                email_box.focus()
                return
            if not password:
                messagebox.showwarning("Missing Password", "Please enter a password.")
                pass_box.focus()
                return
            if not confirm_password:
                messagebox.showwarning("Confirm Password", "Please confirm your password.")
                confirm_pass_box.focus()
                return

            # Validation: Email format
            if not is_valid_email(email):
                messagebox.showerror("Invalid Email", "Please enter a valid email address (e.g. user@example.com).")
                email_box.focus()
                return

            # Validation: Password strength (minimum length)
            if len(password) < 6:
                messagebox.showwarning("Weak Password", "Password must be at least 6 characters long.")
                pass_box.focus()
                return

            # Validation: Password match
            if password != confirm_password:
                messagebox.showerror("Password Mismatch", "Passwords do not match. Please re-enter your password.")
                confirm_pass_box.focus()
                return

            # Validation: Duplicate email check
            existing = fetch_one("SELECT id FROM users WHERE email=%s", (email,))
            if existing:
                messagebox.showerror("Email Exists", "An account with this email address already exists. Please login instead.")
                return

            try:
                run_query(
                    "INSERT INTO users (name, email, password_hash) VALUES (%s,%s,%s)",
                    (name, email, password_hash(password))
                )
                messagebox.showinfo("Registration Successful", "Your account has been created successfully! Please sign in.")
                self.show_user_login()
            except Exception as error:
                messagebox.showerror("Registration Error", "Could not create account:\n" + str(error))

        button(form, "Register", save_user, GREEN).grid(row=6, column=0, columnspan=2, sticky="ew", pady=(18, 6))
        button(form, "Already have an account? Sign In", self.show_user_login, BLUE).grid(row=7, column=0, columnspan=2, sticky="ew", pady=4)
        button(form, "Back to Main Menu", self.show_start, MUTED).grid(row=8, column=0, columnspan=2, sticky="ew", pady=4)

    def build_user_login(self, page):
        form = card(page)
        form.pack(expand=True, ipadx=45, ipady=35)

        label(form, "User Sign In", 24, TEXT, True).grid(row=0, column=0, columnspan=2, pady=(0, 4))
        label(form, "Enter your credentials to access tickets and bookings", 11, MUTED).grid(row=1, column=0, columnspan=2, pady=(0, 18))

        label(form, "Email Address").grid(row=2, column=0, sticky="e", padx=(0, 10), pady=7)
        email_box = entry(form)
        email_box.grid(row=2, column=1, sticky="ew", pady=7, ipady=7)

        label(form, "Password").grid(row=3, column=0, sticky="e", padx=(0, 10), pady=7)
        pass_box = entry(form, show="*")
        pass_box.grid(row=3, column=1, sticky="ew", pady=7, ipady=7)

        captcha_a = random.randint(2, 9)
        captcha_b = random.randint(2, 9)
        label(form, f"Security Check: {captcha_a} + {captcha_b} =").grid(row=4, column=0, sticky="e", padx=(0, 10), pady=7)
        captcha_box = entry(form)
        captcha_box.grid(row=4, column=1, sticky="ew", pady=7, ipady=7)

        form.grid_columnconfigure(1, weight=1)

        otp_label = label(form, "Verification OTP")
        otp_box = entry(form)

        def check_login():
            email = email_box.get().strip().lower()
            password = pass_box.get().strip()
            captcha = captcha_box.get().strip()

            # Validation: Blank fields
            if not email:
                messagebox.showwarning("Missing Email", "Please enter your email address.")
                email_box.focus()
                return
            if not is_valid_email(email):
                messagebox.showerror("Invalid Email", "Please enter a valid email address.")
                email_box.focus()
                return
            if not password:
                messagebox.showwarning("Missing Password", "Please enter your password.")
                pass_box.focus()
                return
            if not captcha:
                messagebox.showwarning("Missing Captcha", "Please solve the security calculation.")
                captcha_box.focus()
                return

            # Validation: Captcha math
            if captcha != str(captcha_a + captcha_b):
                messagebox.showerror("Security Check Failed", "Incorrect answer to the security check. Please try again.")
                captcha_box.delete(0, tk.END)
                captcha_box.focus()
                return

            # Validation: Database user credentials
            user = fetch_one(
                "SELECT * FROM users WHERE email=%s AND password_hash=%s",
                (email, password_hash(password))
            )
            if not user:
                messagebox.showerror("Login Failed", "Invalid email or password. Please check your credentials.")
                return

            self.current_user = user

            # Check if this user account has OTP bypass enabled
            if bool(user.get("bypass")):
                messagebox.showinfo(
                    "Sign In Successful",
                    f"Welcome back, {user['name']}!\n\n(OTP Bypassed: Test account privileges active)"
                )
                self.show_user_home()
                return

            self.login_otp = make_otp()
            body = f"Your Movie Booking Service login OTP is: {self.login_otp}\n\nThis OTP is valid for your current session."
            if send_email(email, "Your Login OTP - Movie Booking Service", body):
                messagebox.showinfo("OTP Dispatched", "A 6-digit verification OTP has been sent to your email address.")
                otp_label.grid(row=6, column=0, sticky="e", padx=(0, 10), pady=7)
                otp_box.grid(row=6, column=1, sticky="ew", pady=7, ipady=7)
                otp_box.focus()
                verify_btn.grid(row=7, column=0, columnspan=2, sticky="ew", pady=6)

        def verify_otp():
            entered_otp = otp_box.get().strip()
            if not entered_otp:
                messagebox.showwarning("Missing OTP", "Please enter the verification OTP sent to your email.")
                otp_box.focus()
                return
            if entered_otp == self.login_otp:
                self.show_user_home()
            else:
                messagebox.showerror("Invalid OTP", "The entered OTP is incorrect. Please check your email and try again.")
                otp_box.focus()

        button(form, "Send OTP / Sign In", check_login, BLUE).grid(row=5, column=0, columnspan=2, sticky="ew", pady=(16, 6))
        verify_btn = button(form, "Verify OTP & Continue", verify_otp, GREEN)
        button(form, "Create New Account", self.show_register, GREEN).grid(row=8, column=0, columnspan=2, sticky="ew", pady=4)
        button(form, "Back to Main Menu", self.show_start, MUTED).grid(row=9, column=0, columnspan=2, sticky="ew", pady=4)
        label(form, "Test Account (No OTP): test@movie.com / test123", 9, GREEN, True).grid(row=10, column=0, columnspan=2, pady=(10, 0))

    def build_admin_login(self, page):
        form = card(page)
        form.pack(expand=True, ipadx=45, ipady=35)

        label(form, "Administrator Sign In", 24, TEXT, True).grid(row=0, column=0, columnspan=2, pady=(0, 4))
        label(form, "Restricted access — Cinema staff & administrators only", 11, MUTED).grid(row=1, column=0, columnspan=2, pady=(0, 18))

        label(form, "Admin Email").grid(row=2, column=0, sticky="e", padx=(0, 10), pady=7)
        email_box = entry(form)
        email_box.grid(row=2, column=1, sticky="ew", pady=7, ipady=7)

        label(form, "Admin Password").grid(row=3, column=0, sticky="e", padx=(0, 10), pady=7)
        pass_box = entry(form, show="*")
        pass_box.grid(row=3, column=1, sticky="ew", pady=7, ipady=7)

        form.grid_columnconfigure(1, weight=1)

        def check_admin_login():
            email = email_box.get().strip().lower()
            password = pass_box.get().strip()

            # Validation: Blank fields
            if not email:
                messagebox.showwarning("Missing Email", "Please enter the admin email address.")
                email_box.focus()
                return
            if not is_valid_email(email):
                messagebox.showerror("Invalid Email", "Please enter a valid email address.")
                email_box.focus()
                return
            if not password:
                messagebox.showwarning("Missing Password", "Please enter the admin password.")
                pass_box.focus()
                return

            # Validation: Admin Credentials
            if email == ADMIN_EMAIL.lower() and password == ADMIN_PASSWORD:
                self.current_user = {"id": 0, "name": "Admin", "email": ADMIN_EMAIL}
                self.show_admin_panel()
            else:
                messagebox.showerror("Authentication Failed", "Invalid administrator email or password.")

        button(form, "Sign In to Admin Panel", check_admin_login, ORANGE).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(16, 6))
        button(form, "Switch to User Portal", self.show_user_login, BLUE).grid(row=5, column=0, columnspan=2, sticky="ew", pady=4)
        button(form, "Back to Main Menu", self.show_start, MUTED).grid(row=6, column=0, columnspan=2, sticky="ew", pady=4)

    def show_user_home(self):
        self.release_held_seats()
        self.switch_page(self.build_user_home)

    def build_user_home(self, page):
        self.add_topbar(
            page, 
            "Welcome, " + self.current_user["name"], 
            self.show_start,
            extra_btn={"text": "My Bookings", "command": self.show_my_bookings}
        )

        header = tk.Frame(page, bg=BG)
        header.pack(fill="x", padx=35, pady=(18, 8))

        top_row = tk.Frame(header, bg=BG)
        top_row.pack(fill="x")
        label(top_row, "Choose a Movie", 23, TEXT, True).pack(side="left")

        # Category filter bar
        filter_bar = tk.Frame(top_row, bg=BG)
        filter_bar.pack(side="right")

        label(header, "Browse trends, upcoming movies and long bored picks with live availability.", 12, MUTED).pack(anchor="w", pady=(2, 0))

        scroll_container = ScrollableFrame(page, bg=BG)
        scroll_container.pack(fill="both", expand=True, padx=(35, 20), pady=(8, 15))
        grid = scroll_container.scrollable_content

        for c in range(3):
            grid.grid_columnconfigure(c, weight=1, uniform="movie_col")

        movies = fetch_all("SELECT * FROM movies ORDER BY id DESC")
        filter_buttons = {}

        def render_movies(filter_tab="All"):
            for child in grid.winfo_children():
                child.destroy()

            def match_filter(m):
                status = (m.get("date_status") or "").strip().lower()
                badge = (m.get("badge") or "").strip()
                cat = (m.get("category") or "").strip().lower()

                if filter_tab == "All":
                    return status != "ended"
                if filter_tab == "Now Showing":
                    return status == "now showing"
                if filter_tab == "Pre-booking":
                    return status == "pre-booking"
                if filter_tab == "Upcoming":
                    return status in ("releasing soon", "pre-booking")
                if filter_tab == "Trends":
                    return badge.lower() == "trending" or cat == "trends"
                return cat == filter_tab.lower()

            filtered = [m for m in movies if match_filter(m)]
            if not filtered:
                empty_card = card(grid)
                empty_card.grid(row=0, column=0, columnspan=3, pady=40, padx=20, sticky="ew")
                label(empty_card, f"No movies found under '{filter_tab}'.", 14, MUTED).pack(pady=20)
                return

            for index, movie in enumerate(filtered):
                movie_card = card(grid)
                movie_card.grid(row=index // 3, column=index % 3, padx=10, pady=10, sticky="nsew", ipadx=12, ipady=12)

                # Dedicated Badge / Ribbon rendering
                render_badge(movie_card, movie.get("badge"))

                label(movie_card, movie["category"], 10, BLUE, True).pack(anchor="w")
                label(movie_card, movie["title"], 18, TEXT, True).pack(anchor="w", pady=(3, 8))
                synopsis_short = textwrap.shorten(movie["synopsis"], width=120, placeholder="...") if len(movie["synopsis"]) > 120 else movie["synopsis"]
                wrapped_label(movie_card, synopsis_short, 10, MUTED, wraplength=280).pack(anchor="w")
                label(movie_card, f'{movie["length_minutes"]} min | {movie["rating"]} | {movie["release_year"]}',
                      10, TEXT, True).pack(anchor="w", pady=8)
                label(movie_card, movie["date_status"], 10, ORANGE, True).pack(anchor="w")
                button(movie_card, "Movie Details", lambda m=movie: self.show_movie_details(m), BLUE).pack(fill="x", pady=(15, 5))
                button(movie_card, "Book Ticket", lambda m=movie: self.show_select_show(m), GREEN).pack(fill="x")

            scroll_container.canvas.yview_moveto(0)

        def set_filter(cat):
            for c_name, b in filter_buttons.items():
                if c_name == cat:
                    b.configure(bg=BLUE, fg="white")
                else:
                    b.configure(bg=PANEL, fg=TEXT)
            render_movies(cat)

        filter_tabs = ["All", "Now Showing", "Pre-booking", "Upcoming", "Trends"]
        for cat in filter_tabs:
            b = tk.Button(
                filter_bar, text=cat, command=lambda c=cat: set_filter(c),
                bg=BLUE if cat == "All" else PANEL,
                fg="white" if cat == "All" else TEXT,
                activebackground=BLUE_DARK if cat == "All" else GREY,
                font=("Segoe UI", 10, "bold"), bd=0, padx=12, pady=4, cursor="hand2",
                highlightthickness=1, highlightbackground="#d1d5db"
            )
            b.pack(side="left", padx=3)
            filter_buttons[cat] = b

        render_movies("All")

    def add_topbar(self, page, title, back_command, extra_btn=None):
        top = tk.Frame(page, bg=PANEL, height=70, highlightthickness=1, highlightbackground="#dbe4ea")
        top.pack(fill="x")
        top.pack_propagate(False)
        label(top, title, 18, TEXT, True).pack(side="left", padx=30)
        button(top, "Back / Logout", back_command, MUTED).pack(side="right", padx=30)
        if extra_btn:
            button(top, extra_btn["text"], extra_btn["command"], BLUE).pack(side="right", padx=(0, 15))
    def show_my_bookings(self):
        self.switch_page(self.build_my_bookings)

    def build_my_bookings(self, page):
        self.add_topbar(page, "My Bookings", self.show_user_home)
        body = tk.Frame(page, bg=BG)
        body.pack(fill="both", expand=True, padx=40, pady=25)

        label(body, "Booking History", 24, TEXT, True).pack(anchor="w")
        label(body, "Review your past and upcoming movie tickets.", 12, MUTED).pack(anchor="w", pady=(0, 15))

        bookings = fetch_all("""
            SELECT b.id as booking_id, b.seats_text, b.snacks_text, b.total_amount, b.created_at,
                   m.title as movie_title, s.show_date, s.show_time,
                   c.name as cinema_name, l.name as location_name
            FROM bookings b
            JOIN shows s ON b.show_id = s.id
            JOIN movies m ON s.movie_id = m.id
            JOIN cinemas c ON s.cinema_id = c.id
            JOIN locations l ON c.location_id = l.id
            WHERE b.user_id = %s
            ORDER BY b.id DESC
        """, (self.current_user["id"],))

        scroll_container = ScrollableFrame(body, bg=BG)
        scroll_container.pack(fill="both", expand=True)
        list_frame = scroll_container.scrollable_content

        if not bookings:
            label(list_frame, "You haven't made any bookings yet.", 13, MUTED).pack(anchor="w", pady=20)
            return

        for b in bookings:
            b_card = card(list_frame)
            b_card.pack(fill="x", pady=8, ipady=10, ipadx=10)
            
            # Header row: Movie Title & Booking ID
            header = tk.Frame(b_card, bg=PANEL)
            header.pack(fill="x", padx=10, pady=(5, 10))
            label(header, b["movie_title"], 16, TEXT, True).pack(side="left")
            label(header, f"Booking ID: #{b['booking_id']}", 11, MUTED).pack(side="right")
            
            # Details
            details = tk.Frame(b_card, bg=PANEL)
            details.pack(fill="x", padx=10)
            
            info_text = f"{b['location_name']} | {b['cinema_name']} | {b['show_date']} | {b['show_time']}"
            label(details, info_text, 12, BLUE, True).pack(anchor="w", pady=(0, 5))
            label(details, f"Seats: {b['seats_text']}", 11, TEXT).pack(anchor="w", pady=2)
            label(details, f"Snacks: {b['snacks_text']}", 11, TEXT).pack(anchor="w", pady=2)
            
            footer = tk.Frame(b_card, bg=PANEL)
            footer.pack(fill="x", padx=10, pady=(10, 5))
            label(footer, f"Total Paid: Rs. {b['total_amount']}", 12, GREEN, True).pack(side="left")
            label(footer, f"Booked on: {b['created_at']}", 10, MUTED).pack(side="right")

    def show_movie_details(self, movie):
        self.selected_movie = movie
        self.switch_page(lambda page: self.build_movie_details(page, movie))

    def build_movie_details(self, page, movie):
        self.add_topbar(page, movie["title"], self.show_user_home)
        details = card(page)
        details.pack(fill="both", expand=True, padx=60, pady=45, ipadx=30, ipady=30)

        render_badge(details, movie.get("badge"), size=10, pady=(0, 10))
        label(details, movie["title"], 30, TEXT, True).pack(anchor="w")
        label(details, f"{movie['category']}  |  Status: {movie['date_status']}", 12, BLUE, True).pack(anchor="w", pady=(2, 15))
        label(details, "Cast: " + movie["movie_cast"], 13).pack(anchor="w", pady=5)
        # Multi-line synopsis with proper text wrapping
        synopsis_frame = tk.Frame(details, bg=PANEL)
        synopsis_frame.pack(anchor="w", fill="x", pady=5)
        label(synopsis_frame, "Synopsis: ", 13, TEXT, True).pack(side="left", anchor="n")
        wrapped_label(synopsis_frame, movie["synopsis"], 13, MUTED, wraplength=700).pack(side="left", fill="x", expand=True, anchor="w")
        label(details, "Length: " + str(movie["length_minutes"]) + " minutes", 13).pack(anchor="w", pady=5)
        label(details, "Rating: " + movie["rating"], 13).pack(anchor="w", pady=5)
        label(details, "Year Released: " + str(movie["release_year"]), 13).pack(anchor="w", pady=5)
        label(details, "Trailer Link: " + str(movie["trailer_link"]), 13, BLUE).pack(anchor="w", pady=5)
        button(details, "Book This Movie", lambda: self.show_select_show(movie), GREEN).pack(anchor="w", pady=25)

    def show_select_show(self, movie):
        self.release_held_seats()
        self.selected_movie = movie
        self.switch_page(lambda page: self.build_select_show(page, movie))

    def build_select_show(self, page, movie):
        self.add_topbar(page, "Select Cinema and Time", self.show_user_home)

        body = tk.Frame(page, bg=BG)
        body.pack(fill="both", expand=True, padx=40, pady=25)

        label(body, movie["title"], 24, TEXT, True).pack(anchor="w")
        label(body, "Nearest locations and one-week show plan with live seat availability", 12, MUTED).pack(anchor="w", pady=(0, 15))

        shows = fetch_all("""
            SELECT shows.*, cinemas.name AS cinema_name, locations.name AS location_name,
                   COUNT(seats.id) AS total_seats,
                   SUM(CASE WHEN seats.status = 'free' THEN 1 ELSE 0 END) AS available_seats
            FROM shows
            JOIN cinemas ON cinemas.id = shows.cinema_id
            JOIN locations ON locations.id = cinemas.location_id
            LEFT JOIN seats ON seats.show_id = shows.id
            WHERE shows.movie_id=%s
            GROUP BY shows.id, cinemas.name, locations.name
            ORDER BY shows.show_date, shows.show_time
        """, (movie["id"],))

        scroll_container = ScrollableFrame(body, bg=BG)
        scroll_container.pack(fill="both", expand=True)
        list_frame = scroll_container.scrollable_content

        if not shows:
            label(list_frame, "No shows scheduled for this movie currently.", 13, MUTED).pack(anchor="w", pady=20)
            return

        for show in shows:
            show_card = card(list_frame)
            show_card.pack(fill="x", pady=6, ipady=7)

            total = int(show["total_seats"] or 0)
            available = int(show["available_seats"] or 0)

            # Left details: Cinema, Location, Date, Time, Price
            left_info = tk.Frame(show_card, bg=PANEL)
            left_info.pack(side="left", padx=14)

            main_text = f'{show["location_name"]} | {show["cinema_name"]} | {show["show_date"]} | {show["show_time"]} | Rs.{show["price"]}'
            label(left_info, main_text, 12, TEXT, True).pack(anchor="w")

            # Dynamic Tickets Remaining Badge
            if available <= 0:
                avail_color = RED
                avail_text = "Sold Out (0 tickets remaining)"
            elif available <= 10:
                avail_color = ORANGE
                avail_text = f"Only {available} tickets remaining (out of {total})!"
            else:
                avail_color = GREEN
                avail_text = f"{available} tickets remaining (out of {total})"

            label(left_info, avail_text, 10, avail_color, True).pack(anchor="w", pady=(2, 0))

            if available > 0:
                button(show_card, "Select Seats", lambda s=show: self.show_seats(s), BLUE).pack(side="right", padx=12)
            else:
                sold_out_btn = tk.Label(show_card, text="Sold Out", bg=GREY, fg=MUTED,
                                        font=("Segoe UI", 11, "bold"), padx=16, pady=9)
                sold_out_btn.pack(side="right", padx=12)

    def show_seats(self, show):
        if self.selected_show and self.selected_show.get("id") != show.get("id"):
            self.release_held_seats()
        self.selected_show = show
        self.switch_page(lambda page: self.build_seats(page, show))

    def build_seats(self, page, show):
        self.add_topbar(page, "Select Seats", self.back_from_seats)

        body = tk.Frame(page, bg=BG)
        body.pack(fill="both", expand=True, padx=40, pady=20)

        # Clear any orphaned held seats without a real user in the DB
        try:
            run_query("""
                UPDATE seats SET status='free', booked_by=NULL 
                WHERE status='held' AND (booked_by IS NULL OR booked_by NOT IN (SELECT id FROM users))
            """)
        except Exception:
            pass

        seats = fetch_all("SELECT * FROM seats WHERE show_id=%s ORDER BY seat_no", (show["id"],))
        total_seats = len(seats)
        free_seats = sum(
            1 for s in seats 
            if s["status"] == "free" or (s["status"] == "held" and s.get("booked_by") == self.current_user["id"])
        )

        top_info = tk.Frame(body, bg=BG)
        top_info.pack(fill="x", pady=(0, 10))

        label(top_info, "Cinema Seating Plan", 24, TEXT, True).pack(side="left")
        avail_badge = f"Tickets Remaining: {free_seats} / {total_seats}"
        label(top_info, avail_badge, 13, GREEN if free_seats > 10 else ORANGE if free_seats > 0 else RED, True).pack(side="right", padx=10)

        label(body, "Booked = red, free = grey, selected = green, in progress = orange",
              12, MUTED).pack(anchor="w", pady=(0, 15))

        screen = tk.Label(body, text="SCREEN", bg="#c7d2fe", fg="#312e81",
                          font=("Segoe UI", 12, "bold"), pady=10)
        screen.pack(fill="x", padx=180, pady=(0, 20))

        seat_area = tk.Frame(body, bg=BG)
        seat_area.pack()
        buttons = {}

        def change_seat(seat, btn):
            seat_no = seat["seat_no"]
            status = seat["status"]
            booked_by = seat.get("booked_by")

            if status == "booked":
                messagebox.showwarning("Seat Booked", f"Seat {seat_no} has already been booked.")
                return

            if status == "held" and booked_by != self.current_user["id"]:
                messagebox.showwarning(
                    "Seat in Progress",
                    f"Seat {seat_no} is currently being booked by another user.\nPlease choose a different seat."
                )
                return

            if seat_no in self.selected_seats:
                self.selected_seats.remove(seat_no)
                if status == "held" and booked_by == self.current_user["id"]:
                    run_query(
                        "UPDATE seats SET status='free', booked_by=NULL WHERE show_id=%s AND seat_no=%s AND booked_by=%s",
                        (show["id"], seat_no, self.current_user["id"])
                    )
                    seat["status"] = "free"
                    seat["booked_by"] = None
                btn.configure(bg=GREY, fg=TEXT)
            else:
                self.selected_seats.append(seat_no)
                btn.configure(bg=GREEN, fg="white")

        for index, seat in enumerate(seats):
            color = GREY
            fg = TEXT
            seat_no = seat["seat_no"]
            is_mine = seat_no in self.selected_seats or (seat["status"] == "held" and seat.get("booked_by") == self.current_user["id"])

            if is_mine:
                color = GREEN
                fg = "white"
                if seat_no not in self.selected_seats:
                    self.selected_seats.append(seat_no)
            elif seat["status"] == "booked":
                color = RED
                fg = "white"
            elif seat["status"] == "held":
                color = ORANGE
                fg = "white"

            btn = tk.Button(
                seat_area, text=seat_no, width=7, height=2,
                bg=color, fg=fg, bd=0, cursor="hand2",
                font=("Segoe UI", 10, "bold")
            )
            btn.configure(command=lambda s=seat, b=btn: change_seat(s, b))
            btn.grid(row=index // 8, column=index % 8, padx=5, pady=5)
            buttons[seat_no] = btn

        bottom = tk.Frame(body, bg=BG)
        bottom.pack(pady=25)

        def go_next():
            if not self.selected_seats:
                messagebox.showwarning("Seats", "Please select at least one seat.")
                return

            # Atomic race-safe hold using a single DB transaction.
            # Each UPDATE only succeeds if the seat is STILL 'free' at that exact moment.
            # cursor.rowcount == 0 means another user won the race for that seat — detected instantly.
            successfully_held = []
            conflict_seats = []

            try:
                db = connect_db()
                cursor = db.cursor()
                for seat_no in self.selected_seats:
                    cursor.execute(
                        "UPDATE seats SET status='held', booked_by=%s "
                        "WHERE show_id=%s AND seat_no=%s AND status='free'",
                        (self.current_user["id"], self.selected_show["id"], seat_no)
                    )
                    if cursor.rowcount == 1:
                        successfully_held.append(seat_no)
                    else:
                        # rowcount=0 means seat was grabbed by another user between our check and now
                        conflict_seats.append(seat_no)

                if conflict_seats and successfully_held:
                    # Roll back any seats we managed to hold since we can't proceed with a partial selection
                    held_ph = ",".join(["%s"] * len(successfully_held))
                    cursor.execute(
                        f"UPDATE seats SET status='free', booked_by=NULL "
                        f"WHERE show_id=%s AND seat_no IN ({held_ph}) AND booked_by=%s",
                        tuple([self.selected_show["id"]] + successfully_held + [self.current_user["id"]])
                    )

                db.commit()
            except Exception as err:
                messagebox.showerror("Error", "Could not reserve seats. Please try again.\n" + str(err))
                return
            finally:
                cursor.close()
                db.close()

            if conflict_seats:
                messagebox.showerror(
                    "Seat Just Taken",
                    "The following seat(s) were grabbed by another user at the same time:\n" +
                    "\n".join(f"  • Seat {s}" for s in conflict_seats) +
                    "\n\nAll your selections have been released. Please choose different seats."
                )
                self.show_seats(self.selected_show)
                return

            # Reset snacks only on fresh forward navigation (not when going Back from payment)
            self.selected_snacks = {}
            self.show_snacks()

        button(bottom, "Continue to Snacks", go_next, GREEN).pack(side="left", padx=8)

    def back_from_seats(self):
        self.release_held_seats()
        self.show_select_show(self.selected_movie)

    def show_snacks(self):
        self.switch_page(self.build_snacks)

    def build_snacks(self, page):
        self.add_topbar(page, "Add Snacks", lambda: self.show_seats(self.selected_show))
        body = tk.Frame(page, bg=BG)
        body.pack(fill="both", expand=True, padx=50, pady=(20, 15))

        label(body, "Food Offers", 24, TEXT, True).pack(anchor="w")
        label(body, "Pick snacks to buy with your ticket.", 12, MUTED).pack(anchor="w", pady=(0, 10))

        bottom_bar = tk.Frame(body, bg=BG)
        bottom_bar.pack(side="bottom", fill="x", pady=(10, 0))

        scroll_container = ScrollableFrame(body, bg=BG)
        scroll_container.pack(fill="both", expand=True)
        snack_list = scroll_container.scrollable_content

        snacks = fetch_all("SELECT * FROM snacks WHERE available='yes'")
        choices = []
        for item in snacks:
            row = card(snack_list)
            row.pack(fill="x", pady=7, ipady=8)
            selected = tk.IntVar()
            qty = tk.IntVar(value=1)
            tk.Checkbutton(row, variable=selected, bg=PANEL, cursor="hand2").pack(side="left", padx=10)
            label(row, item["name"], 13, TEXT, True).pack(side="left")
            label(row, "Rs." + str(item["price"]), 12, BLUE, True).pack(side="left", padx=18)
            label(row, item["offer_text"] or "", 11, MUTED).pack(side="left", padx=10)
            tk.Spinbox(row, from_=1, to=10, width=4, textvariable=qty,
                       font=("Segoe UI", 11)).pack(side="right", padx=15)
            label(row, "Qty").pack(side="right")
            choices.append((item, selected, qty))

        def save_snacks():
            self.selected_snacks = {}
            for item, selected, qty in choices:
                if selected.get() == 1:
                    self.selected_snacks[item["name"]] = {
                        "price": item["price"],
                        "qty": qty.get()
                    }
            self.show_payment()

        button(bottom_bar, "Continue to Payment", save_snacks, GREEN).pack(anchor="e")

    def show_payment(self):
        self.payment_otp = ""
        self.switch_page(self.build_payment)

    def calculate_total(self):
        seat_total = len(self.selected_seats) * int(self.selected_show["price"])
        snack_total = 0
        for item in self.selected_snacks.values():
            snack_total += int(item["price"]) * int(item["qty"])
        return seat_total + snack_total

    def build_payment(self, page):
        self.add_topbar(page, "Payment and Confirmation", self.show_snacks)
        body = card(page)
        body.pack(expand=True, ipadx=45, ipady=35)

        total = self.calculate_total()
        snack_text = self.snack_summary()
        has_bypass = bool(self.current_user.get("bypass"))

        label(body, "Booking Summary", 24, TEXT, True).pack(anchor="w")
        label(body, "Movie: " + self.selected_movie["title"], 13).pack(anchor="w", pady=4)
        label(body, "Seats: " + ", ".join(self.selected_seats), 13).pack(anchor="w", pady=4)
        label(body, "Snacks: " + snack_text, 13).pack(anchor="w", pady=4)
        label(body, "Total Amount: Rs." + str(total), 17, GREEN, True).pack(anchor="w", pady=14)
        if has_bypass:
            label(body, "⚡ Test Account: OTP Verification is Bypassed", 11, GREEN, True).pack(anchor="w", pady=(0, 10))
        else:
            label(body, "Complete payment within 10 minutes.", 11, ORANGE, True).pack(anchor="w", pady=(0, 10))

        otp_box = entry(body)

        otp_sent = [False]

        def send_payment_otp():
            if has_bypass:
                confirm_booking()
                return

            self.payment_otp = make_otp()
            email = self.current_user["email"]
            message = (
                "Your payment confirmation OTP is: " + self.payment_otp +
                "\nMovie: " + self.selected_movie["title"] +
                "\nSeats: " + ", ".join(self.selected_seats) +
                "\nTotal: Rs." + str(total)
            )
            if send_email(email, "Payment OTP and Ticket Details", message):
                if otp_sent[0]:
                    messagebox.showinfo("OTP Resent", "A new OTP has been sent to your email.\nYour previous OTP is now invalid.")
                else:
                    messagebox.showinfo("OTP Sent", "Payment OTP has been sent to your email.")
                otp_sent[0] = True
                otp_box.pack(fill="x", ipady=8, pady=8)
                verify_btn.pack(fill="x", pady=5)
                send_btn.configure(text="Resend OTP", bg=MUTED)

        def confirm_booking():
            if not has_bypass:
                if otp_box.get().strip() != self.payment_otp:
                    messagebox.showerror("Wrong OTP", "Payment OTP is incorrect.")
                    return

            # Validation: Check available seats count before booking
            seat_status = fetch_all(
                "SELECT seat_no, status, booked_by FROM seats WHERE show_id=%s",
                (self.selected_show["id"],)
            )
            available_seats = sum(
                1 for s in seat_status
                if s["status"] == "free" or (s["status"] == "held" and s.get("booked_by") == self.current_user["id"])
            )
            selected_count = len(self.selected_seats)

            if selected_count > available_seats:
                messagebox.showerror(
                    "Not Enough Seats",
                    f"Only {available_seats} tickets are currently available for this show.\n"
                    f"You tried to book {selected_count} seats.\n\n"
                    f"Please reduce your selection or choose a different showtime."
                )
                return

            # Validation: Check if selected seats are still free or held by current user
            current_seats = fetch_all(
                "SELECT seat_no, status, booked_by FROM seats WHERE show_id=%s AND seat_no IN (" +
                ",".join(["%s"] * len(self.selected_seats)) + ")",
                tuple([self.selected_show["id"]] + self.selected_seats)
            )
            for seat in current_seats:
                is_mine = (seat["status"] == "held" and seat.get("booked_by") == self.current_user["id"])
                if seat["status"] != "free" and not is_mine:
                    messagebox.showerror("Seat Taken", "Seat " + seat["seat_no"] + " is no longer available. Please select different seats.")
                    return

            booking_id = run_query("""
                INSERT INTO bookings (user_id, show_id, seats_text, snacks_text, total_amount)
                VALUES (%s,%s,%s,%s,%s)
            """, (
                self.current_user["id"],
                self.selected_show["id"],
                ", ".join(self.selected_seats),
                snack_text,
                total
            ))

            for seat_no in self.selected_seats:
                run_query("""
                    UPDATE seats SET status='booked', booked_by=%s, booking_id=%s
                    WHERE show_id=%s AND seat_no=%s
                """, (self.current_user["id"], booking_id, self.selected_show["id"], seat_no))

            ticket = (
                "Your ticket is confirmed.\n\n"
                "Booking ID: " + str(booking_id) +
                "\nMovie: " + self.selected_movie["title"] +
                "\nCinema: " + self.selected_show["cinema_name"] +
                "\nDate: " + str(self.selected_show["show_date"]) +
                "\nTime: " + self.selected_show["show_time"] +
                "\nSeats: " + ", ".join(self.selected_seats) +
                "\nSnacks: " + snack_text +
                "\nTotal Paid: Rs." + str(total)
            )
            send_email(self.current_user["email"], "Your Movie Ticket", ticket)
            messagebox.showinfo("Confirmed", "Ticket confirmed and emailed.")
            self.selected_seats = []
            self.show_user_home()

        btn_text = "Confirm Ticket & Pay (OTP Bypassed)" if has_bypass else "Send Payment OTP"
        send_btn = button(body, btn_text, send_payment_otp, GREEN if has_bypass else BLUE)
        send_btn.pack(fill="x", pady=(15, 5))
        verify_btn = button(body, "Verify OTP and Confirm Ticket", confirm_booking, GREEN)

    def snack_summary(self):
        if not self.selected_snacks:
            return "No snacks"
        parts = []
        for name, item in self.selected_snacks.items():
            parts.append(name + " x" + str(item["qty"]))
        return ", ".join(parts)

    def show_admin_panel(self):
        self.switch_page(self.build_admin_panel)

    def build_admin_panel(self, page):
        self.add_topbar(page, "Admin Panel", self.show_start)
        body = tk.Frame(page, bg=BG)
        body.pack(fill="both", expand=True, padx=25, pady=20)

        left = tk.Frame(body, bg=BG)
        left.pack(side="left", fill="y", padx=(0, 18))
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        label(left, "Tools", 20, TEXT, True).pack(anchor="w", pady=(0, 12))
        button(left, "Add New Movie", lambda: self.admin_catalog(right), BLUE).pack(fill="x", pady=5)
        button(left, "Edit Movie Details", lambda: self.admin_edit_movie(right), BLUE).pack(fill="x", pady=5)
        button(left, "Delete Movie", lambda: self.admin_delete_movie(right), BLUE).pack(fill="x", pady=5)
        button(left, "New Food Offers", lambda: self.admin_food(right), BLUE).pack(fill="x", pady=5)
        button(left, "Past Queue", lambda: self.admin_queue(right), BLUE).pack(fill="x", pady=5)
        button(left, "Pre-booking", lambda: self.admin_prebooking(right), BLUE).pack(fill="x", pady=5)
        button(left, "Support", lambda: self.admin_support(right), BLUE).pack(fill="x", pady=5)

        self.admin_catalog(right)

    def clear_admin_right(self, right):
        for child in right.winfo_children():
            child.destroy()

    def admin_catalog(self, right):
        self.clear_admin_right(right)
        panel = card(right)
        panel.pack(fill="both", expand=True, ipadx=20, ipady=15)

        scroll = ScrollableFrame(panel, bg=PANEL)
        scroll.pack(fill="both", expand=True)
        content = scroll.scrollable_content

        label(content, "Add New Movie", 22, TEXT, True).pack(anchor="w", pady=(0, 4))
        label(content, "Enter movie details and configure ribbon badge & release status.", 11, MUTED).pack(anchor="w", pady=(0, 15))

        form = tk.Frame(content, bg=PANEL)
        form.pack(fill="x")
        form.grid_columnconfigure(1, weight=1)

        # 1. Title
        label(form, "Title *").grid(row=0, column=0, sticky="w", pady=6)
        title_box = entry(form)
        title_box.grid(row=0, column=1, sticky="ew", pady=6, ipady=5)

        # 2. Movie Badge / Ribbon
        label(form, "Movie Badge / Ribbon").grid(row=1, column=0, sticky="w", pady=6)
        badge_cb = dropdown(form, MOVIE_BADGES, default="None")
        badge_cb.grid(row=1, column=1, sticky="w", pady=6)

        # 3. Category (with Other text option)
        label(form, "Category *").grid(row=2, column=0, sticky="w", pady=6)
        cat_frame = tk.Frame(form, bg=PANEL)
        cat_frame.grid(row=2, column=1, sticky="ew", pady=6)
        cat_cb = dropdown(cat_frame, MOVIE_CATEGORIES, default="Action")
        cat_cb.pack(side="left")
        other_cat_box = entry(cat_frame)

        def on_cat_change(event=None):
            if cat_cb.get() == "Other":
                other_cat_box.pack(side="left", padx=(10, 0), fill="x", expand=True)
                other_cat_box.focus()
            else:
                other_cat_box.pack_forget()

        cat_cb.bind("<<ComboboxSelected>>", on_cat_change)

        # 4. Cast
        label(form, "Cast").grid(row=3, column=0, sticky="w", pady=6)
        cast_box = entry(form)
        cast_box.grid(row=3, column=1, sticky="ew", pady=6, ipady=5)

        # 5. Synopsis
        label(form, "Synopsis").grid(row=4, column=0, sticky="nw", pady=6)
        synopsis_box = tk.Text(
            form, font=("Segoe UI", 11), bd=0, relief="flat",
            bg="#f8fafc", fg=TEXT, insertbackground=TEXT, height=3,
            highlightbackground="#d1d5db", highlightthickness=1, wrap="word"
        )
        synopsis_box.grid(row=4, column=1, sticky="ew", pady=6)

        # 6. Length Minutes
        label(form, "Length (Minutes)").grid(row=5, column=0, sticky="w", pady=6)
        length_box = entry(form)
        length_box.grid(row=5, column=1, sticky="ew", pady=6, ipady=5)

        # 7. Rating
        label(form, "Rating (e.g. 4.5/5)").grid(row=6, column=0, sticky="w", pady=6)
        rating_box = entry(form)
        rating_box.grid(row=6, column=1, sticky="ew", pady=6, ipady=5)

        # 8. Release Year
        label(form, "Release Year").grid(row=7, column=0, sticky="w", pady=6)
        year_box = entry(form)
        year_box.grid(row=7, column=1, sticky="ew", pady=6, ipady=5)

        # 9. Trailer Link
        label(form, "Trailer Link (URL)").grid(row=8, column=0, sticky="w", pady=6)
        trailer_box = entry(form)
        trailer_box.grid(row=8, column=1, sticky="ew", pady=6, ipady=5)

        # 10. Date Status
        label(form, "Date Status *").grid(row=9, column=0, sticky="w", pady=6)
        status_cb = dropdown(form, MOVIE_DATE_STATUSES, default="Now Showing")
        status_cb.grid(row=9, column=1, sticky="w", pady=6)

        def save_movie():
            title = title_box.get().strip()
            if not title:
                messagebox.showwarning("Missing Field", "Please enter the movie title.")
                title_box.focus()
                return

            category = other_cat_box.get().strip() if cat_cb.get() == "Other" else cat_cb.get().strip()
            if not category:
                category = "Other"

            badge = badge_cb.get().strip()
            cast = cast_box.get().strip()
            synopsis = synopsis_box.get("1.0", "end-1c").strip()
            rating = rating_box.get().strip() or "N/A"
            trailer = trailer_box.get().strip()
            date_status = status_cb.get().strip()

            try:
                length_val = int(length_box.get().strip()) if length_box.get().strip() else 120
            except ValueError:
                messagebox.showerror("Invalid Value", "Length in minutes must be a valid number.")
                length_box.focus()
                return

            try:
                year_val = int(year_box.get().strip()) if year_box.get().strip() else 2026
            except ValueError:
                messagebox.showerror("Invalid Value", "Release year must be a valid number (e.g. 2026).")
                year_box.focus()
                return

            try:
                run_query("""
                    INSERT INTO movies
                    (title, badge, category, movie_cast, synopsis, length_minutes, rating, release_year, trailer_link, date_status)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    title, badge, category, cast, synopsis,
                    length_val, rating, year_val, trailer, date_status
                ))
                messagebox.showinfo("Saved", f'Movie "{title}" added to the catalog.')
                self.admin_catalog(right)
            except Exception as error:
                messagebox.showerror("Database Error", "Could not save movie:\n" + str(error))

        button(content, "Save Movie", save_movie, GREEN).pack(anchor="w", pady=(15, 10))

    def admin_delete_movie(self, right):
        self.clear_admin_right(right)
        panel = card(right)
        panel.pack(fill="both", expand=True, ipadx=25, ipady=20)
        label(panel, "Delete Movie", 22, TEXT, True).pack(anchor="w", pady=(0, 12))
        label(panel, "Select a movie to permanently remove it and all its showtimes, seats and bookings.",
              12, MUTED).pack(anchor="w", pady=(0, 15))

        movies = fetch_all("SELECT id, title, category, date_status FROM movies ORDER BY id")
        if not movies:
            label(panel, "No movies in the catalog.", 13, MUTED).pack(anchor="w", pady=20)
            return

        scroll = ScrollableFrame(panel, bg=PANEL)
        scroll.pack(fill="both", expand=True)
        content = scroll.scrollable_content

        for idx, movie in enumerate(movies, start=1):
            row = tk.Frame(content, bg=PANEL)
            row.pack(fill="x", pady=5)
            text = f'{idx}. {movie["title"]}  [{movie["category"]}] - {movie["date_status"]}'
            label(row, text, 12).pack(side="left", padx=(0, 10))
            button(row, "Delete", lambda m=movie: self.confirm_delete_movie(m, right), RED).pack(side="right")

    def confirm_delete_movie(self, movie, right):
        answer = messagebox.askyesno(
            "Confirm Delete",
            f'Are you sure you want to delete "{movie["title"]}"?\n\n'
            "This will also remove all associated showtimes, seat records and bookings.\n"
            "This action cannot be undone."
        )
        if not answer:
            return

        db = connect_db()
        cursor = db.cursor()
        try:
            # Collect show IDs for this movie
            cursor.execute("SELECT id FROM shows WHERE movie_id = %s", (movie["id"],))
            show_ids = [row[0] for row in cursor.fetchall()]

            if show_ids:
                placeholders = ",".join(["%s"] * len(show_ids))

                # Delete seats linked to those shows
                cursor.execute(
                    f"DELETE FROM seats WHERE show_id IN ({placeholders})",
                    tuple(show_ids)
                )

                # Delete bookings linked to those shows
                cursor.execute(
                    f"DELETE FROM bookings WHERE show_id IN ({placeholders})",
                    tuple(show_ids)
                )

            # Delete shows for this movie
            cursor.execute("DELETE FROM shows WHERE movie_id = %s", (movie["id"],))

            # Delete the movie itself
            cursor.execute("DELETE FROM movies WHERE id = %s", (movie["id"],))

            db.commit()
            messagebox.showinfo("Deleted", f'Movie "{movie["title"]}" and all related records have been deleted.')
            # Refresh the panel to reflect the change
            self.admin_delete_movie(right)
        except Exception as error:
            db.rollback()
            messagebox.showerror("Error", "Could not delete movie:\n" + str(error))
        finally:
            cursor.close()
            db.close()

    def admin_edit_movie(self, right, selected_movie_id=None):
        self.clear_admin_right(right)
        panel = card(right)
        panel.pack(fill="both", expand=True, ipadx=20, ipady=15)

        scroll = ScrollableFrame(panel, bg=PANEL)
        scroll.pack(fill="both", expand=True)
        content = scroll.scrollable_content

        label(content, "Edit Movie Details", 22, TEXT, True).pack(anchor="w", pady=(0, 4))
        label(content, "Select any movie to populate all 10 fields and update them with a single save.", 11, MUTED).pack(anchor="w", pady=(0, 15))

        movies = fetch_all("SELECT * FROM movies ORDER BY id")
        if not movies:
            label(content, "No movies available in the catalog.", 13, MUTED).pack(anchor="w", pady=20)
            return

        movie_map = {f"#{m['id']}: {m['title']} [{m.get('date_status') or 'Now Showing'}]": m for m in movies}
        selector_options = list(movie_map.keys())

        selector_frame = tk.Frame(content, bg=PANEL)
        selector_frame.pack(fill="x", pady=(0, 15))
        label(selector_frame, "Select Movie: ", 12, TEXT, True).pack(side="left")

        default_sel = selector_options[0]
        if selected_movie_id:
            for opt, m in movie_map.items():
                if m["id"] == selected_movie_id:
                    default_sel = opt
                    break

        selector_cb = ttk.Combobox(
            selector_frame, values=selector_options, state="readonly",
            font=("Segoe UI", 11), width=45
        )
        selector_cb.set(default_sel)
        selector_cb.pack(side="left", padx=(5, 10))

        form = tk.Frame(content, bg=PANEL)
        form.pack(fill="x")
        form.grid_columnconfigure(1, weight=1)

        # 1. Title
        label(form, "Title *").grid(row=0, column=0, sticky="w", pady=6)
        title_box = entry(form)
        title_box.grid(row=0, column=1, sticky="ew", pady=6, ipady=5)

        # 2. Movie Badge / Ribbon
        label(form, "Movie Badge / Ribbon").grid(row=1, column=0, sticky="w", pady=6)
        badge_cb = dropdown(form, MOVIE_BADGES, default="None")
        badge_cb.grid(row=1, column=1, sticky="w", pady=6)

        # 3. Category (with Other text option)
        label(form, "Category *").grid(row=2, column=0, sticky="w", pady=6)
        cat_frame = tk.Frame(form, bg=PANEL)
        cat_frame.grid(row=2, column=1, sticky="ew", pady=6)
        cat_cb = dropdown(cat_frame, MOVIE_CATEGORIES, default="Action")
        cat_cb.pack(side="left")
        other_cat_box = entry(cat_frame)

        def on_cat_change(event=None):
            if cat_cb.get() == "Other":
                other_cat_box.pack(side="left", padx=(10, 0), fill="x", expand=True)
                other_cat_box.focus()
            else:
                other_cat_box.pack_forget()

        cat_cb.bind("<<ComboboxSelected>>", on_cat_change)

        # 4. Cast
        label(form, "Cast").grid(row=3, column=0, sticky="w", pady=6)
        cast_box = entry(form)
        cast_box.grid(row=3, column=1, sticky="ew", pady=6, ipady=5)

        # 5. Synopsis
        label(form, "Synopsis").grid(row=4, column=0, sticky="nw", pady=6)
        synopsis_box = tk.Text(
            form, font=("Segoe UI", 11), bd=0, relief="flat",
            bg="#f8fafc", fg=TEXT, insertbackground=TEXT, height=3,
            highlightbackground="#d1d5db", highlightthickness=1, wrap="word"
        )
        synopsis_box.grid(row=4, column=1, sticky="ew", pady=6)

        # 6. Length Minutes
        label(form, "Length (Minutes)").grid(row=5, column=0, sticky="w", pady=6)
        length_box = entry(form)
        length_box.grid(row=5, column=1, sticky="ew", pady=6, ipady=5)

        # 7. Rating
        label(form, "Rating (e.g. 4.5/5)").grid(row=6, column=0, sticky="w", pady=6)
        rating_box = entry(form)
        rating_box.grid(row=6, column=1, sticky="ew", pady=6, ipady=5)

        # 8. Release Year
        label(form, "Release Year").grid(row=7, column=0, sticky="w", pady=6)
        year_box = entry(form)
        year_box.grid(row=7, column=1, sticky="ew", pady=6, ipady=5)

        # 9. Trailer Link
        label(form, "Trailer Link (URL)").grid(row=8, column=0, sticky="w", pady=6)
        trailer_box = entry(form)
        trailer_box.grid(row=8, column=1, sticky="ew", pady=6, ipady=5)

        # 10. Date Status
        label(form, "Date Status *").grid(row=9, column=0, sticky="w", pady=6)
        status_cb = dropdown(form, MOVIE_DATE_STATUSES, default="Now Showing")
        status_cb.grid(row=9, column=1, sticky="w", pady=6)

        current_editing_id = [None]

        def load_movie(m):
            current_editing_id[0] = m["id"]

            title_box.delete(0, tk.END)
            title_box.insert(0, m["title"] or "")

            cur_badge = str(m.get("badge") or "None").strip()
            badge_cb.set(cur_badge if cur_badge in MOVIE_BADGES else "None")

            cur_cat = str(m.get("category") or "Action").strip()
            if cur_cat in MOVIE_CATEGORIES[:-1]:
                cat_cb.set(cur_cat)
                other_cat_box.delete(0, tk.END)
                other_cat_box.pack_forget()
            else:
                cat_cb.set("Other")
                other_cat_box.delete(0, tk.END)
                other_cat_box.insert(0, cur_cat)
                other_cat_box.pack(side="left", padx=(10, 0), fill="x", expand=True)

            cast_box.delete(0, tk.END)
            cast_box.insert(0, m["movie_cast"] or "")

            synopsis_box.delete("1.0", tk.END)
            synopsis_box.insert("1.0", m["synopsis"] or "")

            length_box.delete(0, tk.END)
            length_box.insert(0, str(m["length_minutes"] or 120))

            rating_box.delete(0, tk.END)
            rating_box.insert(0, m["rating"] or "")

            year_box.delete(0, tk.END)
            year_box.insert(0, str(m["release_year"] or 2026))

            trailer_box.delete(0, tk.END)
            trailer_box.insert(0, m["trailer_link"] or "")

            cur_status = str(m.get("date_status") or "Now Showing").strip()
            status_cb.set(cur_status if cur_status in MOVIE_DATE_STATUSES else "Now Showing")

        def on_selector_change(event=None):
            selected_str = selector_cb.get()
            if selected_str in movie_map:
                load_movie(movie_map[selected_str])

        selector_cb.bind("<<ComboboxSelected>>", on_selector_change)
        load_movie(movie_map[default_sel])

        def save_changes():
            m_id = current_editing_id[0]
            if not m_id:
                return

            title = title_box.get().strip()
            if not title:
                messagebox.showwarning("Missing Field", "Movie title cannot be empty.")
                title_box.focus()
                return

            category = other_cat_box.get().strip() if cat_cb.get() == "Other" else cat_cb.get().strip()
            if not category:
                category = "Other"

            badge = badge_cb.get().strip()
            cast = cast_box.get().strip()
            synopsis = synopsis_box.get("1.0", "end-1c").strip()
            rating = rating_box.get().strip() or "N/A"
            trailer = trailer_box.get().strip()
            date_status = status_cb.get().strip()

            try:
                length_val = int(length_box.get().strip()) if length_box.get().strip() else 120
            except ValueError:
                messagebox.showerror("Invalid Value", "Length in minutes must be a valid integer.")
                length_box.focus()
                return

            try:
                year_val = int(year_box.get().strip()) if year_box.get().strip() else 2026
            except ValueError:
                messagebox.showerror("Invalid Value", "Release year must be a valid integer.")
                year_box.focus()
                return

            try:
                run_query("""
                    UPDATE movies SET
                        title=%s, badge=%s, category=%s, movie_cast=%s, synopsis=%s,
                        length_minutes=%s, rating=%s, release_year=%s, trailer_link=%s, date_status=%s
                    WHERE id=%s
                """, (
                    title, badge, category, cast, synopsis,
                    length_val, rating, year_val, trailer, date_status,
                    m_id
                ))
                messagebox.showinfo("Saved", f'Movie "{title}" updated successfully.')
                self.admin_edit_movie(right, selected_movie_id=m_id)
            except Exception as error:
                messagebox.showerror("Database Error", "Could not update movie:\n" + str(error))

        btn_row = tk.Frame(content, bg=PANEL)
        btn_row.pack(anchor="w", pady=(18, 10))
        button(btn_row, "Save Changes", save_changes, GREEN).pack(side="left", padx=(0, 10))
        button(btn_row, "Reset Form", lambda: load_movie(movie_map[selector_cb.get()]), MUTED).pack(side="left")

    def admin_dates(self, right):
        self.admin_edit_movie(right)

    def admin_food(self, right):
        self.clear_admin_right(right)
        panel = card(right)
        panel.pack(fill="both", expand=True, ipadx=25, ipady=20)
        label(panel, "New Food Offers", 22, TEXT, True).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        name_box = entry(panel)
        price_box = entry(panel)
        offer_box = entry(panel)
        label(panel, "Snack Name").grid(row=1, column=0, sticky="w", pady=8)
        name_box.grid(row=1, column=1, sticky="ew", ipady=7)
        label(panel, "Price").grid(row=2, column=0, sticky="w", pady=8)
        price_box.grid(row=2, column=1, sticky="ew", ipady=7)
        label(panel, "Offer Text").grid(row=3, column=0, sticky="w", pady=8)
        offer_box.grid(row=3, column=1, sticky="ew", ipady=7)
        panel.grid_columnconfigure(1, weight=1)

        def add_snack():
            name = name_box.get().strip()
            price_str = price_box.get().strip()
            offer = offer_box.get().strip()

            if not name:
                messagebox.showwarning("Missing Field", "Please enter a snack name.")
                name_box.focus()
                return
            if not price_str:
                messagebox.showwarning("Missing Field", "Please enter a price.")
                price_box.focus()
                return
            try:
                price_val = int(price_str)
                if price_val <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid Price", "Price must be a positive whole number (e.g. 150).")
                price_box.focus()
                return

            try:
                run_query(
                    "INSERT INTO snacks (name, price, offer_text) VALUES (%s,%s,%s)",
                    (name, price_val, offer)
                )
                messagebox.showinfo("Saved", f'Snack "{name}" added successfully.')
                name_box.delete(0, tk.END)
                price_box.delete(0, tk.END)
                offer_box.delete(0, tk.END)
                name_box.focus()
            except Exception as error:
                messagebox.showerror("Database Error", "Could not add snack:\n" + str(error))

        button(panel, "Add Snack Offer", add_snack, GREEN).grid(row=4, column=0, columnspan=2, sticky="ew", pady=14)

    def admin_queue(self, right):
        self.clear_admin_right(right)
        panel = card(right)
        panel.pack(fill="both", expand=True, ipadx=25, ipady=20)
        label(panel, "Past Booking Queue", 22, TEXT, True).pack(anchor="w", pady=(0, 12))

        rows = fetch_all("""
            SELECT bookings.*, users.name, movies.title
            FROM bookings
            JOIN users ON users.id = bookings.user_id
            JOIN shows ON shows.id = bookings.show_id
            JOIN movies ON movies.id = shows.movie_id
            ORDER BY bookings.id DESC
        """)
        scroll = ScrollableFrame(panel, bg=PANEL)
        scroll.pack(fill="both", expand=True, pady=(10, 0))
        content = scroll.scrollable_content

        for item in rows:
            text = f'#{item["id"]} | {item["name"]} | {item["title"]} | Seats {item["seats_text"]} | Rs.{item["total_amount"]}'
            label(content, text, 11).pack(anchor="w", pady=4)

    def admin_prebooking(self, right):
        self.clear_admin_right(right)
        panel = card(right)
        panel.pack(fill="both", expand=True, ipadx=25, ipady=20)
        label(panel, "Pre-booking Movies", 22, TEXT, True).pack(anchor="w", pady=(0, 4))
        label(panel, "Movies appear here ONLY when their Date Status is strictly set to 'Pre-booking'.",
              11, MUTED).pack(anchor="w", pady=(0, 15))

        # Strict filtering: date_status = 'Pre-booking'
        rows = fetch_all("""
            SELECT id, title, category, badge, release_year, date_status
            FROM movies
            WHERE date_status = 'Pre-booking'
            ORDER BY id DESC
        """)

        count_text = f"{len(rows)} Movie{'s' if len(rows) != 1 else ''} in Pre-booking"
        label(panel, count_text, 12, ORANGE, True).pack(anchor="w", pady=(0, 10))

        if not rows:
            empty_frame = tk.Frame(panel, bg=PANEL)
            empty_frame.pack(fill="both", expand=True, pady=40)
            label(empty_frame, "No movies currently in Pre-booking status.", 14, MUTED, True).pack(pady=4)
            label(empty_frame, "When a movie's Date Status is set to 'Pre-booking' in Edit Movie Details, it will appear here.\nChanging its status to 'Now Showing' or 'Releasing Soon' immediately removes it.",
                  11, MUTED).pack()
            return

        scroll = ScrollableFrame(panel, bg=PANEL)
        scroll.pack(fill="both", expand=True)
        content = scroll.scrollable_content

        for item in rows:
            row = tk.Frame(content, bg=BG, padx=14, pady=10)
            row.pack(fill="x", pady=6)

            left_box = tk.Frame(row, bg=BG)
            left_box.pack(side="left")

            render_badge(left_box, item.get("badge"), size=8, pady=(0, 4))
            label(left_box, f"#{item['id']} - {item['title']}", 13, TEXT, True).pack(anchor="w")
            details_str = f"Category: {item['category']}  |  Year: {item['release_year']}  |  Status: {item['date_status']}"
            label(left_box, details_str, 10, MUTED).pack(anchor="w", pady=(2, 0))

            button(
                row, "Edit Movie",
                lambda m_id=item["id"]: self.admin_edit_movie(right, selected_movie_id=m_id),
                BLUE
            ).pack(side="right", padx=5)

    def admin_support(self, right):
        self.clear_admin_right(right)
        panel = card(right)
        panel.pack(fill="both", expand=True, ipadx=25, ipady=20)
        label(panel, "Support / Chatbot Tab", 22, TEXT, True).pack(anchor="w", pady=(0, 12))
        label(panel, "Simple support area for future chatbot messages.", 12, MUTED).pack(anchor="w")


def main():
    try:
        setup_database()
    except Exception as error:
        messagebox.showerror(
            "Database Error",
            "Please start MySQL and check DB settings in main.py.\n\n" + str(error)
        )
        return

    root = tk.Tk()
    MovieBookingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()


