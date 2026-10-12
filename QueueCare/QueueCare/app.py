"""QueueCare - Barangay Health Center Appointment & Queue System (Flask + SQLite)"""
import os
import sqlite3
from datetime import date
from functools import wraps

from flask import (Flask, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = "change-this-secret-key"          # change before real use
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "queuecare.db")

SLOTS = ["08:00", "09:00", "10:00", "11:00", "13:00", "14:00", "15:00", "16:00"]
STATUSES = ["Booked", "Waiting", "In Consultation", "Done", "Cancelled"]


# ---------------------------------------------------------------- database
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'patient'
    );
    CREATE TABLE IF NOT EXISTS services(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        provider TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS appointments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        service_id INTEGER NOT NULL,
        appt_date TEXT NOT NULL,
        slot TEXT NOT NULL,
        reason TEXT NOT NULL,
        queue_no INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'Booked',
        notes TEXT DEFAULT '',
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(service_id) REFERENCES services(id)
    );
    """)
    if not db.execute("SELECT 1 FROM users WHERE role='staff'").fetchone():
        db.execute("INSERT INTO users(name,email,phone,password,role) VALUES (?,?,?,?,?)",
                   ("Health Center Staff", "staff@queuecare.com", "",
                    generate_password_hash("staff123"), "staff"))
    if not db.execute("SELECT 1 FROM services").fetchone():
        db.executemany("INSERT INTO services(name,provider) VALUES (?,?)", [
            ("General Check-up", "Dr. Maria Santos"),
            ("Prenatal Care", "Midwife Ana Reyes"),
            ("Immunization", "Nurse Jose Cruz"),
            ("Dental Consultation", "Dr. Paolo Lim"),
        ])
    db.commit()
    db.close()


# ------------------------------------------------------------ access control
def login_required(view):
    @wraps(view)
    def wrapper(*a, **kw):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return view(*a, **kw)
    return wrapper


def staff_required(view):
    @wraps(view)
    def wrapper(*a, **kw):
        if session.get("role") != "staff":
            flash("Staff access only.", "error")
            return redirect(url_for("index"))
        return view(*a, **kw)
    return wrapper


# ------------------------------------------------------------------- pages
@app.route("/")

def index():
    db = get_db()
    today = date.today().isoformat()
    total = db.execute("SELECT COUNT(*) FROM appointments WHERE appt_date=? AND status!='Cancelled'",
                       (today,)).fetchone()[0]
    services = db.execute("SELECT * FROM services").fetchall()
    return render_template("index.html", total=total, services=services)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        pw = request.form.get("password", "")
        if not name or not email or len(pw) < 6:
            flash("Fill in all fields. Password must be at least 6 characters.", "error")
            return render_template("register.html")
        try:
            db = get_db()
            db.execute("INSERT INTO users(name,email,phone,password) VALUES (?,?,?,?)",
                       (name, email, phone, generate_password_hash(pw)))
            db.commit()
        except sqlite3.IntegrityError:
            flash("That email is already registered.", "error")
            return render_template("register.html")
        flash("Account created! You can now log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password"], pw):
            session.clear()
            session.update(user_id=user["id"], name=user["name"], role=user["role"])
            return redirect(url_for("staff" if user["role"] == "staff" else "my"))
        flash("Wrong email or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ------------------------------------------------------------- patient side
@app.route("/api/slots")
@login_required
def api_slots():
    rows = get_db().execute(
        "SELECT slot FROM appointments WHERE service_id=? AND appt_date=? AND status!='Cancelled'",
        (request.args.get("service_id"), request.args.get("date"))).fetchall()
    return jsonify(all=SLOTS, taken=[r["slot"] for r in rows])


@app.route("/book", methods=["GET", "POST"])
@login_required
def book():
    if session["role"] == "staff":
        return redirect(url_for("staff"))
    db = get_db()
    services = db.execute("SELECT * FROM services").fetchall()
    today = date.today().isoformat()
    if request.method == "POST":
        sid = request.form.get("service_id")
        d = request.form.get("appt_date", "")
        slot = request.form.get("slot")
        reason = request.form.get("reason", "").strip()
        if not (sid and d and slot and reason):
            flash("Please complete every field, including a time slot.", "error")
        elif d < today:
            flash("You can't book a date in the past.", "error")
        elif slot not in SLOTS:
            flash("Invalid time slot.", "error")
        elif db.execute("SELECT 1 FROM appointments WHERE service_id=? AND appt_date=? AND slot=? "
                        "AND status!='Cancelled'", (sid, d, slot)).fetchone():
            flash("Sorry, that slot was just taken. Please pick another.", "error")
        elif db.execute("SELECT 1 FROM appointments WHERE user_id=? AND service_id=? AND appt_date=? "
                        "AND status!='Cancelled'", (session["user_id"], sid, d)).fetchone():
            flash("You already have this service booked on that date.", "error")
        else:
            qn = db.execute("SELECT COUNT(*) FROM appointments WHERE appt_date=? AND status!='Cancelled'",
                            (d,)).fetchone()[0] + 1
            db.execute("INSERT INTO appointments(user_id,service_id,appt_date,slot,reason,queue_no) "
                       "VALUES (?,?,?,?,?,?)", (session["user_id"], sid, d, slot, reason, qn))
            db.commit()
            flash(f"Booked! Your queue number for {d} is #{qn}.", "success")
            return redirect(url_for("my"))
    return render_template("book.html", services=services, today=today)


@app.route("/my")
@login_required
def my():
    rows = get_db().execute(
        "SELECT a.*, s.name AS service, s.provider FROM appointments a "
        "JOIN services s ON s.id=a.service_id WHERE a.user_id=? "
        "ORDER BY a.appt_date DESC, a.slot DESC", (session["user_id"],)).fetchall()
    return render_template("my.html", rows=rows, today=date.today().isoformat())


@app.route("/cancel/<int:appt_id>", methods=["POST"])
@login_required
def cancel(appt_id):
    db = get_db()
    db.execute("UPDATE appointments SET status='Cancelled' WHERE id=? AND user_id=? AND status='Booked'",
               (appt_id, session["user_id"]))
    db.commit()
    flash("Appointment cancelled.", "success")
    return redirect(url_for("my"))


# --------------------------------------------------------------- staff side
@app.route("/staff")
@login_required
@staff_required
def staff():
    d = request.args.get("date") or date.today().isoformat()
    q = request.args.get("q", "").strip()
    sql = ("SELECT a.*, u.name AS patient, u.phone, s.name AS service FROM appointments a "
           "JOIN users u ON u.id=a.user_id JOIN services s ON s.id=a.service_id "
           "WHERE a.appt_date=? AND u.name LIKE ? ORDER BY a.slot, a.queue_no")
    rows = get_db().execute(sql, (d, f"%{q}%")).fetchall()
    counts = {s: sum(1 for r in rows if r["status"] == s) for s in STATUSES}
    return render_template("staff.html", rows=rows, d=d, q=q, counts=counts, statuses=STATUSES)


@app.route("/staff/update/<int:appt_id>", methods=["POST"])
@login_required
@staff_required
def update(appt_id):
    status = request.form.get("status")
    notes = request.form.get("notes", "").strip()
    if status in STATUSES:
        db = get_db()
        db.execute("UPDATE appointments SET status=?, notes=? WHERE id=?", (status, notes, appt_id))
        db.commit()
        flash("Record updated.", "success")
    return redirect(request.referrer or url_for("staff"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
