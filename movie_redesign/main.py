import hashlib
import os
import random
import re
import secrets
import smtplib
import time
from datetime import datetime
from email.message import EmailMessage
from functools import wraps

import mysql.connector
from flask import Flask, jsonify, redirect, render_template, request, session, url_for

# ------------------------- SETTINGS -------------------------
# Existing database name is intentionally preserved.
DB_HOST = os.getenv("MOVIE_DB_HOST", "localhost")
DB_USER = os.getenv("MOVIE_DB_USER", "root")
DB_PASSWORD = os.getenv("MOVIE_DB_PASSWORD", "srinath")
DB_NAME = "movie_booking_db"

EMAIL_ADDRESS = os.getenv("MOVIE_EMAIL_ADDRESS", "srinaath25@gmail.com")
EMAIL_APP_PASSWORD = os.getenv("MOVIE_EMAIL_APP_PASSWORD", "")
SMTP_SERVER = os.getenv("MOVIE_SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("MOVIE_SMTP_PORT", "587"))

ADMIN_EMAIL = os.getenv("MOVIE_ADMIN_EMAIL", "admin@movie.com")
ADMIN_PASSWORD = os.getenv("MOVIE_ADMIN_PASSWORD", "admin123")
SECRET_KEY = os.getenv("MOVIE_SECRET_KEY", "replace-this-in-production")

MOVIE_CATEGORIES = [
    "Action", "Drama", "Comedy", "Thriller", "Sci-Fi", "Romance",
    "Animation", "Horror", "Adventure", "Fantasy", "Crime", "Other"
]
MOVIE_DATE_STATUSES = ["Now Showing", "Pre-booking", "Releasing Soon", "Ended"]
MOVIE_BADGES = ["None", "Trending", "Blockbuster Run", "Critic's Choice", "Housefull"]

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["JSON_SORT_KEYS"] = False

# ------------------------- DATABASE -------------------------
def password_hash(password):
    return hashlib.sha256(password.encode()).hexdigest()


def connect_db():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    )


def fetch_all(query, values=()):
    db = connect_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(query, values)
        return cursor.fetchall()
    finally:
        cursor.close()
        db.close()


def fetch_one(query, values=()):
    db = connect_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(query, values)
        return cursor.fetchone()
    finally:
        cursor.close()
        db.close()


def run_query(query, values=()):
    db = connect_db()
    cursor = db.cursor()
    try:
        cursor.execute(query, values)
        db.commit()
        return cursor.lastrowid
    finally:
        cursor.close()
        db.close()


def is_valid_email(email):
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))


def make_otp():
    """Create a cryptographically stronger 6-digit OTP."""
    return str(secrets.randbelow(900000) + 100000)


def normalize_card_number(value):
    return re.sub(r"\D", "", value or "")


def luhn_valid(card_number):
    """Validate the card checksum without storing the card number."""
    digits = normalize_card_number(card_number)
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    parity = len(digits) % 2
    for index, char in enumerate(digits):
        digit = int(char)
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def card_brand(card_number):
    """Return a common card network when the number matches its prefix/length."""
    digits = normalize_card_number(card_number)
    length = len(digits)
    if re.match(r"^4", digits) and length in (13, 16, 19):
        return "Visa"
    if (re.match(r"^(5[1-5])", digits) or
            re.match(r"^(22[2-9][0-9]|2[3-6][0-9]{2}|27[01][0-9]|2720)", digits)) and length == 16:
        return "Mastercard"
    if re.match(r"^3[47]", digits) and length == 15:
        return "American Express"
    if (re.match(r"^(6011|65|64[4-9])", digits) and 16 <= length <= 19):
        return "Discover"
    if re.match(r"^(60|65|81|82|508)", digits) and 16 <= length <= 19:
        return "RuPay"
    return None


def validate_card(card_number, expiry, cvv):
    digits = normalize_card_number(card_number)
    brand = card_brand(digits)
    if not brand or not luhn_valid(digits):
        return False, "Enter a valid card number for a supported card network."
    if not re.fullmatch(r"(0[1-9]|1[0-2])\s*/\s*([0-9]{2}|[0-9]{4})", expiry or ""):
        return False, "Enter expiry in MM/YY format."
    month, year = [part.strip() for part in expiry.split("/")]
    year_num = int(year) + (2000 if len(year) == 2 else 0)
    now = datetime.now()
    if year_num < now.year or (year_num == now.year and int(month) < now.month):
        return False, "The card expiry date has passed."
    cvv_pattern = r"\d{4}" if brand == "American Express" else r"\d{3}"
    if not re.fullmatch(cvv_pattern, cvv or ""):
        return False, "Enter a valid security code for the selected card."
    return True, brand


def validate_upi(upi_id):
    value = (upi_id or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,255}@[a-z][a-z0-9.-]{1,63}", value):
        return False
    return True


def send_email(to_email, subject, body):
    # Email remains server-side. If SMTP settings are absent, fail cleanly.
    if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD:
        app.logger.warning("Email settings are not configured; email was not sent.")
        return False
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
    except Exception:
        app.logger.exception("Email delivery failed")
        return False


# ------------------------- AUTH / STATE -------------------------
def user_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper


def current_user():
    return session.get("user")


def release_held_seats():
    user = current_user()
    show_id = session.get("selected_show_id")
    seats = session.get("selected_seats", [])
    if user and show_id and seats:
        placeholders = ",".join(["%s"] * len(seats))
        run_query(
            f"UPDATE seats SET status='free', booked_by=NULL "
            f"WHERE show_id=%s AND seat_no IN ({placeholders}) "
            f"AND status='held' AND booked_by=%s",
            tuple([show_id] + seats + [user["id"]]),
        )
    session["selected_seats"] = []


def selected_movie():
    movie_id = session.get("selected_movie_id")
    if not movie_id:
        return None
    return fetch_one("SELECT * FROM movies WHERE id=%s", (movie_id,))


def selected_show():
    show_id = session.get("selected_show_id")
    if not show_id:
        return None
    rows = fetch_all("""
        SELECT shows.*, cinemas.name AS cinema_name, locations.name AS location_name,
               COUNT(seats.id) AS total_seats,
               SUM(CASE WHEN seats.status = 'free' THEN 1 ELSE 0 END) AS available_seats
        FROM shows
        JOIN cinemas ON cinemas.id = shows.cinema_id
        JOIN locations ON locations.id = cinemas.location_id
        LEFT JOIN seats ON seats.show_id = shows.id
        WHERE shows.id=%s
        GROUP BY shows.id, cinemas.name, locations.name
    """, (show_id,))
    return rows[0] if rows else None


@app.context_processor
def inject_globals():
    return {
        "session_user": current_user(),
        "is_admin": bool(session.get("admin")),
        "year_now": datetime.now().year,
    }


# ------------------------- PUBLIC -------------------------
@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    try:
        row = fetch_one("SELECT 1 AS ok")
        return jsonify({"ok": bool(row and row["ok"] == 1)})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503


# ------------------------- USER AUTH -------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        a, b = random.randint(2, 9), random.randint(2, 9)
        session["captcha_a"] = a
        session["captcha_b"] = b
        return render_template("login.html", captcha_a=a, captcha_b=b)

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()
    captcha = request.form.get("captcha", "").strip()

    if not email:
        return render_template("login.html", error="Please enter your email address.", captcha_a=session.get("captcha_a"), captcha_b=session.get("captcha_b"))
    if not is_valid_email(email):
        return render_template("login.html", error="Please enter a valid email address.", captcha_a=session.get("captcha_a"), captcha_b=session.get("captcha_b"))
    if not password:
        return render_template("login.html", error="Please enter your password.", captcha_a=session.get("captcha_a"), captcha_b=session.get("captcha_b"))
    if not captcha:
        return render_template("login.html", error="Please solve the security calculation.", captcha_a=session.get("captcha_a"), captcha_b=session.get("captcha_b"))
    if captcha != str(session.get("captcha_a", 0) + session.get("captcha_b", 0)):
        return render_template("login.html", error="Incorrect answer to the security check.", captcha_a=session.get("captcha_a"), captcha_b=session.get("captcha_b"))

    user = fetch_one("SELECT * FROM users WHERE email=%s AND password_hash=%s", (email, password_hash(password)))
    if not user:
        return render_template("login.html", error="Invalid email or password.", captcha_a=session.get("captcha_a"), captcha_b=session.get("captcha_b"))

    user_payload = {"id": user["id"], "name": user["name"], "email": user["email"], "bypass": bool(user.get("bypass"))}
    if bool(user.get("bypass")):
        session["user"] = user_payload
        return redirect(url_for("home"))

    session["login_user_pending"] = user_payload
    otp = make_otp()
    session["login_otp"] = otp
    if not send_email(email, "Your Login OTP - Movie Booking Service", f"Your Movie Booking Service login OTP is: {otp}\n\nThis OTP is valid for your current session."):
        session.pop("user", None)
        return render_template("login.html", error="Could not send the login OTP. Check the server email settings.", captcha_a=session.get("captcha_a"), captcha_b=session.get("captcha_b"))
    session["login_otp_pending"] = True
    return render_template("login.html", otp_pending=True, email=email, captcha_a=session.get("captcha_a"), captcha_b=session.get("captcha_b"))


@app.post("/login/verify")
def verify_login_otp():
    if request.form.get("otp", "").strip() != session.get("login_otp"):
        pending = session.get("login_user_pending", {})
        return render_template("login.html", error="The entered OTP is incorrect.", otp_pending=True, email=pending.get("email", ""), captcha_a=session.get("captcha_a"), captcha_b=session.get("captcha_b"))
    session["user"] = session.pop("login_user_pending", None)
    session.pop("login_otp", None)
    session.pop("login_otp_pending", None)
    return redirect(url_for("home"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()
    confirm = request.form.get("confirm_password", "").strip()

    if not name:
        return render_template("register.html", error="Please enter your full name.")
    if not email or not is_valid_email(email):
        return render_template("register.html", error="Please enter a valid email address.")
    if not password:
        return render_template("register.html", error="Please enter a password.")
    if len(password) < 6:
        return render_template("register.html", error="Password must be at least 6 characters long.")
    if password != confirm:
        return render_template("register.html", error="Passwords do not match.")
    if fetch_one("SELECT id FROM users WHERE email=%s", (email,)):
        return render_template("register.html", error="An account with this email address already exists. Please login instead.")
    try:
        run_query("INSERT INTO users (name, email, password_hash) VALUES (%s,%s,%s)", (name, email, password_hash(password)))
        return redirect(url_for("login"))
    except Exception as exc:
        return render_template("register.html", error="Could not create account: " + str(exc))


@app.get("/logout")
def logout():
    release_held_seats()
    session.clear()
    return redirect(url_for("index"))


# ------------------------- USER FLOW -------------------------
@app.get("/home")
@user_required
def home():
    release_held_seats()
    movies = fetch_all("SELECT * FROM movies ORDER BY id DESC")
    return render_template("home.html", movies=movies)


@app.get("/movie/<int:movie_id>")
@user_required
def movie_details(movie_id):
    movie = fetch_one("SELECT * FROM movies WHERE id=%s", (movie_id,))
    if not movie:
        return redirect(url_for("home"))
    session["selected_movie_id"] = movie_id
    return render_template("movie_details.html", movie=movie)


@app.get("/shows/<int:movie_id>")
@user_required
def shows(movie_id):
    movie = fetch_one("SELECT * FROM movies WHERE id=%s", (movie_id,))
    if not movie:
        return redirect(url_for("home"))
    release_held_seats()
    session["selected_movie_id"] = movie_id
    rows = fetch_all("""
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
    """, (movie_id,))
    return render_template("shows.html", movie=movie, shows=rows)


@app.get("/seats/<int:show_id>")
@user_required
def seats(show_id):
    if session.get("selected_show_id") and session.get("selected_show_id") != show_id:
        release_held_seats()
    show = fetch_one("""
        SELECT shows.*, cinemas.name AS cinema_name, locations.name AS location_name
        FROM shows
        JOIN cinemas ON cinemas.id = shows.cinema_id
        JOIN locations ON locations.id = cinemas.location_id
        WHERE shows.id=%s
    """, (show_id,))
    if not show:
        return redirect(url_for("home"))
    session["selected_show_id"] = show_id
    session["selected_movie_id"] = show["movie_id"]
    try:
        run_query("""
            UPDATE seats SET status='free', booked_by=NULL
            WHERE status='held' AND (booked_by IS NULL OR booked_by NOT IN (SELECT id FROM users))
        """)
    except Exception:
        pass
    seat_rows = fetch_all("SELECT * FROM seats WHERE show_id=%s ORDER BY seat_no", (show_id,))
    return render_template("seats.html", show=show, seats=seat_rows, selected=session.get("selected_seats", []))


@app.post("/seats/continue")
@user_required
def hold_seats():
    selected = request.form.getlist("seats")
    show_id = session.get("selected_show_id")
    user = current_user()
    if not selected or not show_id:
        return redirect(url_for("seats", show_id=show_id))

    successfully_held = []
    conflict_seats = []
    db = connect_db()
    cursor = db.cursor()
    try:
        for seat_no in selected:
            cursor.execute(
                "UPDATE seats SET status='held', booked_by=%s WHERE show_id=%s AND seat_no=%s AND status='free'",
                (user["id"], show_id, seat_no),
            )
            if cursor.rowcount == 1:
                successfully_held.append(seat_no)
            else:
                conflict_seats.append(seat_no)
        if conflict_seats and successfully_held:
            ph = ",".join(["%s"] * len(successfully_held))
            cursor.execute(
                f"UPDATE seats SET status='free', booked_by=NULL WHERE show_id=%s AND seat_no IN ({ph}) AND booked_by=%s",
                tuple([show_id] + successfully_held + [user["id"]]),
            )
        db.commit()
    except Exception as exc:
        db.rollback()
        return render_template("seats.html", show=selected_show(), seats=fetch_all("SELECT * FROM seats WHERE show_id=%s ORDER BY seat_no", (show_id,)), selected=selected, error="Could not reserve seats. Please try again. " + str(exc))
    finally:
        cursor.close()
        db.close()

    if conflict_seats:
        return render_template("seats.html", show=selected_show(), seats=fetch_all("SELECT * FROM seats WHERE show_id=%s ORDER BY seat_no", (show_id,)), selected=[], error="These seats were taken at the same time: " + ", ".join(conflict_seats))
    session["selected_seats"] = selected
    session["selected_snacks"] = {}
    return redirect(url_for("snacks"))


@app.get("/snacks")
@user_required
def snacks():
    if not session.get("selected_show_id") or not session.get("selected_seats"):
        return redirect(url_for("home"))
    rows = fetch_all("SELECT * FROM snacks WHERE available='yes'")
    return render_template("snacks.html", snacks=rows)


@app.post("/snacks")
@user_required
def save_snacks():
    rows = fetch_all("SELECT * FROM snacks WHERE available='yes'")
    selected = {}
    for item in rows:
        qty_raw = request.form.get(f"qty_{item['id']}", "0")
        try:
            qty = int(qty_raw)
        except ValueError:
            qty = 0
        if request.form.get(f"snack_{item['id']}") == "on" and qty > 0:
            selected[item["name"]] = {"price": item["price"], "qty": qty}
    session["selected_snacks"] = selected
    return redirect(url_for("payment"))


def calculate_total():
    show = selected_show()
    seat_total = len(session.get("selected_seats", [])) * int(show["price"])
    snack_total = sum(int(item["price"]) * int(item["qty"]) for item in session.get("selected_snacks", {}).values())
    return seat_total + snack_total


def snack_summary():
    selected = session.get("selected_snacks", {})
    if not selected:
        return "No snacks"
    return ", ".join(name + " x" + str(item["qty"]) for name, item in selected.items())


@app.get("/payment")
@user_required
def payment():
    if not session.get("selected_show_id") or not session.get("selected_seats"):
        return redirect(url_for("home"))
    return render_template(
        "payment.html",
        movie=selected_movie(),
        show=selected_show(),
        total=calculate_total(),
        snack_summary=snack_summary(),
        otp_sent=False,
        selected_method=session.get("payment_method", "card"),
    )


@app.post("/payment/otp")
@user_required
def payment_otp():
    # A resend uses the already verified payment method/reference and does not
    # ask the browser to send card details again.
    resend = request.form.get("resend") == "1"
    if resend and session.get("payment_method") in {"card", "upi"} and session.get("payment_reference"):
        method = session["payment_method"]
        reference = session["payment_reference"]
        movie = selected_movie()
        show = selected_show()
        total = calculate_total()
        return _send_payment_otp(method, reference, movie, show, total)

    method = request.form.get("payment_method", "").strip().lower()
    card_number = request.form.get("card_number", "").strip()
    card_expiry = request.form.get("card_expiry", "").strip()
    card_cvv = request.form.get("card_cvv", "").strip()
    upi_id = request.form.get("upi_id", "").strip().lower()

    if method not in {"card", "upi"}:
        error = "Choose Card or UPI to continue."
    elif method == "card":
        valid, result = validate_card(card_number, card_expiry, card_cvv)
        error = None if valid else result
    else:
        error = None if validate_upi(upi_id) else "Enter a valid UPI ID, for example name@provider."

    movie = selected_movie()
    show = selected_show()
    total = calculate_total()
    common = dict(
        movie=movie, show=show, total=total, snack_summary=snack_summary(),
        selected_method=method or "card", otp_sent=False,
    )
    if error:
        return render_template("payment.html", error=error, **common)

    # Never store full card numbers, CVV, or the full UPI ID in the session/database.
    session["payment_method"] = method
    if method == "card":
        digits = normalize_card_number(card_number)
        session["payment_reference"] = f"{card_brand(digits)} ending {digits[-4:]}"
    else:
        local, provider = upi_id.split("@", 1)
        masked = (local[:2] + "••••" + local[-1:]) if len(local) > 3 else "••••"
        session["payment_reference"] = masked + "@" + provider

    return _send_payment_otp(method, session["payment_reference"], movie, show, total)


def _send_payment_otp(method, reference, movie, show, total):
    otp = make_otp()
    session["payment_otp"] = otp
    session["payment_otp_expires"] = time.time() + 600
    email = current_user()["email"]
    message = (
        f"Your Movie Booking payment verification OTP is: {otp}\n\n"
        f"Payment method: {method.upper()}\n"
        f"Reference: {reference}\n"
        f"Movie: {movie['title']}\n"
        f"Seats: {', '.join(session.get('selected_seats', []))}\n"
        f"Total: Rs.{total}\n\n"
        "This OTP expires in 10 minutes. Do not share it with anyone."
    )
    if not send_email(email, "Movie Booking Payment Verification OTP", message):
        session.pop("payment_otp", None)
        session.pop("payment_otp_expires", None)
        return render_template(
            "payment.html", movie=movie, show=show, total=total,
            snack_summary=snack_summary(), selected_method=method, otp_sent=False,
            error="Could not send the payment OTP. Check the server email settings."
        )
    return render_template(
        "payment.html", movie=movie, show=show, total=total,
        snack_summary=snack_summary(), selected_method=method, otp_sent=True,
        payment_reference=reference
    )


@app.post("/payment/confirm")
@user_required
def confirm_booking():
    user = current_user()
    entered_otp = request.form.get("otp", "").strip()
    expected_otp = session.get("payment_otp")
    expires = session.get("payment_otp_expires", 0)
    method = session.get("payment_method")
    reference = session.get("payment_reference")

    if method not in {"card", "upi"} or not reference:
        return render_template(
            "payment.html", movie=selected_movie(), show=selected_show(),
            total=calculate_total(), snack_summary=snack_summary(),
            selected_method="card", error="Payment details were not verified. Please restart payment.",
        )
    if not expected_otp or time.time() > float(expires) or entered_otp != expected_otp:
        return render_template(
            "payment.html", movie=selected_movie(), show=selected_show(),
            total=calculate_total(), snack_summary=snack_summary(),
            selected_method=method, otp_sent=True, payment_reference=reference,
            error="The payment OTP is invalid or expired. Request a new OTP.",
        )

    show_id = session.get("selected_show_id")
    selected = session.get("selected_seats", [])
    seat_status = fetch_all("SELECT seat_no, status, booked_by FROM seats WHERE show_id=%s", (show_id,))
    available_seats = sum(1 for s in seat_status if s["status"] == "free" or (s["status"] == "held" and s.get("booked_by") == user["id"]))
    if len(selected) > available_seats:
        return render_template("payment.html", movie=selected_movie(), show=selected_show(), total=calculate_total(), snack_summary=snack_summary(), selected_method=method, otp_sent=True, payment_reference=reference, error="Not enough seats are currently available.")

    ph = ",".join(["%s"] * len(selected))
    current_seats = fetch_all(f"SELECT seat_no, status, booked_by FROM seats WHERE show_id=%s AND seat_no IN ({ph})", tuple([show_id] + selected))
    for seat in current_seats:
        is_mine = seat["status"] == "held" and seat.get("booked_by") == user["id"]
        if seat["status"] != "free" and not is_mine:
            return render_template("payment.html", movie=selected_movie(), show=selected_show(), total=calculate_total(), snack_summary=snack_summary(), selected_method=method, otp_sent=True, payment_reference=reference, error=f"Seat {seat['seat_no']} is no longer available.")

    total = calculate_total()
    snack_text = snack_summary()
    booking_id = run_query("""
        INSERT INTO bookings (user_id, show_id, seats_text, snacks_text, total_amount)
        VALUES (%s,%s,%s,%s,%s)
    """, (user["id"], show_id, ", ".join(selected), snack_text, total))

    for seat_no in selected:
        run_query("""
            UPDATE seats SET status='booked', booked_by=%s, booking_id=%s
            WHERE show_id=%s AND seat_no=%s
        """, (user["id"], booking_id, show_id, seat_no))

    show = selected_show()
    movie = selected_movie()
    ticket = (
        "Your ticket is confirmed.\n\n"
        + "Booking ID: " + str(booking_id)
        + "\nMovie: " + movie["title"]
        + "\nCinema: " + show["cinema_name"]
        + "\nDate: " + str(show["show_date"])
        + "\nTime: " + str(show["show_time"])
        + "\nSeats: " + ", ".join(selected)
        + "\nSnacks: " + snack_text
        + "\nTotal Paid: Rs." + str(total)
    )
    email_sent = send_email(user["email"], "Your Movie Ticket", ticket)
    session["selected_seats"] = []
    session["selected_snacks"] = {}
    session.pop("payment_otp", None)
    session.pop("payment_otp_expires", None)
    session.pop("payment_method", None)
    session.pop("payment_reference", None)
    return render_template("ticket.html", booking_id=booking_id, movie=movie, show=show, seats=selected, snack_summary=snack_text, total=total, email_sent=email_sent)


@app.get("/bookings")
@user_required
def bookings():
    rows = fetch_all("""
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
    """, (current_user()["id"],))
    return render_template("bookings.html", bookings=rows)


# ------------------------- ADMIN -------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "GET":
        return render_template("admin_login.html")
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()
    if email == ADMIN_EMAIL.lower() and password == ADMIN_PASSWORD:
        session["admin"] = True
        session["user"] = None
        return redirect(url_for("admin_dashboard"))
    return render_template("admin_login.html", error="Invalid administrator email or password.")


@app.get("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("index"))


@app.get("/admin")
@admin_required
def admin_dashboard():
    stats = {
        "movies": fetch_one("SELECT COUNT(*) AS n FROM movies")["n"],
        "shows": fetch_one("SELECT COUNT(*) AS n FROM shows")["n"],
        "bookings": fetch_one("SELECT COUNT(*) AS n FROM bookings")["n"],
        "snacks": fetch_one("SELECT COUNT(*) AS n FROM snacks")["n"],
    }
    return render_template("admin.html", stats=stats, section="dashboard")


@app.route("/admin/movies/new", methods=["GET", "POST"])
@admin_required
def admin_new_movie():
    if request.method == "GET":
        return render_template("admin.html", section="new_movie", categories=MOVIE_CATEGORIES, statuses=MOVIE_DATE_STATUSES, badges=MOVIE_BADGES)
    title = request.form.get("title", "").strip()
    category = request.form.get("category", "").strip()
    badge = request.form.get("badge", "None").strip()
    cast = request.form.get("movie_cast", "").strip()
    synopsis = request.form.get("synopsis", "").strip()
    rating = request.form.get("rating", "").strip() or "N/A"
    trailer = request.form.get("trailer_link", "").strip()
    date_status = request.form.get("date_status", "Now Showing").strip()
    try:
        length_val = int(request.form.get("length_minutes", "120") or 120)
        year_val = int(request.form.get("release_year", str(datetime.now().year)) or datetime.now().year)
    except ValueError:
        return render_template("admin.html", section="new_movie", error="Length and release year must be valid integers.", categories=MOVIE_CATEGORIES, statuses=MOVIE_DATE_STATUSES, badges=MOVIE_BADGES)
    if not title:
        return render_template("admin.html", section="new_movie", error="Please enter the movie title.", categories=MOVIE_CATEGORIES, statuses=MOVIE_DATE_STATUSES, badges=MOVIE_BADGES)
    try:
        run_query("""
            INSERT INTO movies (title, badge, category, movie_cast, synopsis, length_minutes, rating, release_year, trailer_link, date_status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (title, badge, category, cast, synopsis, length_val, rating, year_val, trailer, date_status))
        return redirect(url_for("admin_dashboard"))
    except Exception as exc:
        return render_template("admin.html", section="new_movie", error="Could not save movie: " + str(exc), categories=MOVIE_CATEGORIES, statuses=MOVIE_DATE_STATUSES, badges=MOVIE_BADGES)


@app.get("/admin/movies/edit")
@admin_required
def admin_edit_movie():
    movies = fetch_all("SELECT * FROM movies ORDER BY id")
    movie_id = request.args.get("id", type=int)
    selected = next((m for m in movies if m["id"] == movie_id), movies[0] if movies else None)
    return render_template("admin.html", section="edit_movie", movies=movies, movie=selected, categories=MOVIE_CATEGORIES, statuses=MOVIE_DATE_STATUSES, badges=MOVIE_BADGES)


@app.post("/admin/movies/edit")
@admin_required
def admin_save_movie():
    m_id = request.form.get("id", type=int)
    if not m_id:
        return redirect(url_for("admin_edit_movie"))
    title = request.form.get("title", "").strip()
    category = request.form.get("category", "").strip() or "Other"
    badge = request.form.get("badge", "None").strip()
    cast = request.form.get("movie_cast", "").strip()
    synopsis = request.form.get("synopsis", "").strip()
    rating = request.form.get("rating", "").strip() or "N/A"
    trailer = request.form.get("trailer_link", "").strip()
    date_status = request.form.get("date_status", "Now Showing").strip()
    try:
        length_val = int(request.form.get("length_minutes", "120") or 120)
        year_val = int(request.form.get("release_year", str(datetime.now().year)) or datetime.now().year)
        run_query("""
            UPDATE movies SET title=%s, badge=%s, category=%s, movie_cast=%s, synopsis=%s,
            length_minutes=%s, rating=%s, release_year=%s, trailer_link=%s, date_status=%s WHERE id=%s
        """, (title, badge, category, cast, synopsis, length_val, rating, year_val, trailer, date_status, m_id))
        return redirect(url_for("admin_edit_movie", id=m_id))
    except Exception as exc:
        return redirect(url_for("admin_edit_movie", id=m_id, error=str(exc)))


@app.route("/admin/movies/delete", methods=["GET", "POST"])
@admin_required
def admin_delete_movie():
    movies = fetch_all("SELECT id, title, category, date_status FROM movies ORDER BY id")
    if request.method == "POST":
        movie_id = request.form.get("id", type=int)
        db = connect_db()
        cursor = db.cursor()
        try:
            cursor.execute("SELECT id FROM shows WHERE movie_id=%s", (movie_id,))
            show_ids = [row[0] for row in cursor.fetchall()]
            if show_ids:
                ph = ",".join(["%s"] * len(show_ids))
                cursor.execute(f"DELETE FROM seats WHERE show_id IN ({ph})", tuple(show_ids))
                cursor.execute(f"DELETE FROM bookings WHERE show_id IN ({ph})", tuple(show_ids))
            cursor.execute("DELETE FROM shows WHERE movie_id=%s", (movie_id,))
            cursor.execute("DELETE FROM movies WHERE id=%s", (movie_id,))
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            cursor.close()
            db.close()
        return redirect(url_for("admin_delete_movie"))
    return render_template("admin.html", section="delete_movie", movies=movies)


@app.route("/admin/snacks", methods=["GET", "POST"])
@admin_required
def admin_snacks():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        price = request.form.get("price", "").strip()
        offer = request.form.get("offer_text", "").strip()
        try:
            price_val = int(price)
            if not name or price_val <= 0:
                raise ValueError
            run_query("INSERT INTO snacks (name, price, offer_text) VALUES (%s,%s,%s)", (name, price_val, offer))
        except ValueError:
            return render_template("admin.html", section="snacks", error="Snack name and positive whole-number price are required.")
        except Exception as exc:
            return render_template("admin.html", section="snacks", error="Could not add snack: " + str(exc))
    return render_template("admin.html", section="snacks")


@app.get("/admin/queue")
@admin_required
def admin_queue():
    rows = fetch_all("""
        SELECT bookings.*, users.name, movies.title
        FROM bookings
        JOIN users ON users.id = bookings.user_id
        JOIN shows ON shows.id = bookings.show_id
        JOIN movies ON movies.id = shows.movie_id
        ORDER BY bookings.id DESC
    """)
    return render_template("admin.html", section="queue", rows=rows)


@app.get("/admin/prebooking")
@admin_required
def admin_prebooking():
    rows = fetch_all("""
        SELECT id, title, category, badge, release_year, date_status FROM movies
        WHERE date_status='Pre-booking' ORDER BY id DESC
    """)
    return render_template("admin.html", section="prebooking", rows=rows)


@app.get("/admin/support")
@admin_required
def admin_support():
    return render_template("admin.html", section="support")


if __name__ == "__main__":
    # No CREATE DATABASE, ALTER TABLE, seat reset, or seed operation is executed.
    # The existing movie_booking_db schema/data are treated as authoritative.
    app.run(host="127.0.0.1", port=int(os.getenv("MOVIE_PORT", "5000")), debug=False)
