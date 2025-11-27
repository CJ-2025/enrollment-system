from flask import Flask, render_template, request, redirect, session
from flask_bcrypt import Bcrypt
from db import get_db_connection

app = Flask(__name__)
app.secret_key = "secretkey123"
bcrypt = Bcrypt(app)


@app.route("/")
def landing():
    return render_template("landing.html")

# ----------------------------------
# LOGIN
# ----------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()

        if user and bcrypt.check_password_hash(user["password"], password):
            if user["role"] != "admin":
                conn.close()
                return "Access Denied", 403

            session["role"] = "admin"
            session["username"] = user["username"]
            session["user_id"] = user["id"]
            conn.close()
            return redirect("/admin/dashboard")

        conn.close()
        return "Invalid username or password"

    return render_template("admin/login.html")

# ----------------------------------
# ADMIN DASHBOARD
# ----------------------------------
@app.route("/admin/dashboard")
def admin_dashboard():
    if session.get("role") != "admin":
        return "Access Denied", 403

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # Total students
    cur.execute("SELECT COUNT(*) AS total FROM students")
    total_students = cur.fetchone()["total"]

    # Active users
    cur.execute("SELECT COUNT(*) AS total FROM users")
    active_users = cur.fetchone()["total"]

    # Admin count
    cur.execute("SELECT COUNT(*) AS total FROM users WHERE role='admin'")
    total_admins = cur.fetchone()["total"]

    # Program statistics (for pie chart)
    cur.execute("""
        SELECT p.name AS program_name, COUNT(s.id) AS count
        FROM programs p
        LEFT JOIN students s ON s.program_id = p.id
        GROUP BY p.id
        ORDER BY p.name
    """)
    program_stats = cur.fetchall()

    program_labels = [p["program_name"] for p in program_stats]
    program_counts = [p["count"] for p in program_stats]

    # Recent students
    cur.execute("""
        SELECT s.id, s.student_id, s.first_name, s.last_name,
               s.year_level, s.created_at AS date,
               p.name AS program_name
        FROM students s
        LEFT JOIN programs p ON s.program_id = p.id
        ORDER BY s.id DESC
        LIMIT 5
    """)
    recent_students = cur.fetchall()

    conn.close()

    # Example enrollment chart (dummy months)
    months = ["Jan", "Feb", "Mar", "Apr", "May"]
    enroll_counts = [5, 10, 7, 15, 20]

    return render_template(
        "admin/dashboard_admin.html",
        total_students=total_students,
        active_users=active_users,
        total_admins=total_admins,
        months=months,
        enroll_counts=enroll_counts,
        program_labels=program_labels,
        program_counts=program_counts,
        recent_students=recent_students
    )


# ----------------------------------
# ADMIN - USER CRUD
# ----------------------------------
@app.route("/admin/users")
def admin_users():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()

    # Group by role
    users_by_role = {
        "admin": [],
        "registrar": [],
        "cashier": [],
        "student": []
    }

    for user in users:
        role = user["role"].lower()

        # Ensure the role exists in dictionary
        if role in users_by_role:
            users_by_role[role].append(user)

    conn.close()

    return render_template("admin/users.html", users_by_role=users_by_role)


@app.route("/admin/users/add", methods=["GET","POST"])
def admin_add_user():
    if session.get("role") != "admin":
        return "Access Denied", 403

    if request.method=="POST":
        username = request.form["username"]
        password = request.form["password"]
        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        if cur.fetchone():
            conn.close()
            return "Username already exists!"

        cur.execute("INSERT INTO users (username,password,role) VALUES (%s,%s,'admin')",(username,hashed_pw))
        conn.commit()
        conn.close()
        return redirect("/admin/users")

    return render_template("admin/users_add.html", role="admin")

@app.route("/admin/users/edit/<int:id>", methods=["GET","POST"])
def admin_edit_user(id):
    if session.get("role") != "admin":
        return "Access Denied", 403

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if request.method=="POST":
        username = request.form["username"]
        password = request.form.get("password")

        cur.execute("SELECT * FROM users WHERE username=%s AND id!=%s", (username, id))
        if cur.fetchone():
            conn.close()
            return "Username already exists!"

        if password:
            hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
            cur.execute("UPDATE users SET username=%s, password=%s WHERE id=%s", (username, hashed_pw, id))
        else:
            cur.execute("UPDATE users SET username=%s WHERE id=%s", (username, id))

        conn.commit()
        conn.close()
        return redirect("/admin/users")

    cur.execute("SELECT * FROM users WHERE id=%s", (id,))
    user = cur.fetchone()
    conn.close()
    return render_template("admin/users_edit.html", user=user)

@app.route("/admin/users/delete/<int:id>")
def admin_delete_user(id):
    if session.get("role") != "admin":
        return "Access Denied", 403

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id=%s",(id,))
    conn.commit()
    conn.close()
    return redirect("/admin/users")

# ----------------------------------
# ADMIN - STUDENT LIST PAGE
# ----------------------------------
@app.route("/admin/students")
def admin_students():
    if session.get("role") != "admin":
        return "Access Denied", 403

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # Fetch students with program name
    cur.execute("""
        SELECT s.id, s.student_id, s.first_name, s.last_name, s.middle_name,
               s.birthdate, s.address, s.contact, s.year_level, s.created_at,
               p.name AS program_name, p.id AS program_id
        FROM students s
        LEFT JOIN programs p ON s.program_id = p.id
        ORDER BY s.id DESC
    """)
    students = cur.fetchall()

    # Fetch program id + name for dropdowns
    cur.execute("SELECT id, name FROM programs ORDER BY name")
    all_programs = cur.fetchall()

    conn.close()

    return render_template("admin/students.html",
                           students=students,
                           all_programs=all_programs)

# ----------------------------------
# ADMIN - STUDENT CRUD
# ----------------------------------
@app.route("/admin/students/add", methods=["POST"])
def admin_add_student():
    if session.get("role") != "admin":
        return "Access Denied", 403

    student_id = request.form["student_id"]
    first_name = request.form["first_name"]
    middle_name = request.form.get("middle_name")
    last_name = request.form["last_name"]
    birthdate = request.form.get("birthdate")  # format YYYY-MM-DD
    address = request.form.get("address")
    contact = request.form.get("contact")
    program_id = request.form["program_id"]
    year_level = request.form.get("year_level") or 1
    user_id = session.get("user_id")  # optional: who created the record

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO students
        (student_id, first_name, middle_name, last_name, birthdate, address, contact, program_id, year_level, user_id, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
    """, (student_id, first_name, middle_name, last_name, birthdate, address, contact, program_id, year_level, user_id))
    conn.commit()
    conn.close()
    return redirect("/admin/students")


@app.route("/admin/students/edit/<int:id>", methods=["POST"])
def admin_edit_student(id):
    if session.get("role") != "admin":
        return "Access Denied", 403

    student_id = request.form["student_id"]
    first_name = request.form["first_name"]
    middle_name = request.form.get("middle_name")
    last_name = request.form["last_name"]
    birthdate = request.form.get("birthdate")  # format YYYY-MM-DD
    address = request.form.get("address")
    contact = request.form.get("contact")
    program_id = request.form["program_id"]
    year_level = request.form.get("year_level") or 1

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE students
        SET student_id=%s, first_name=%s, middle_name=%s, last_name=%s,
            birthdate=%s, address=%s, contact=%s, program_id=%s, year_level=%s
        WHERE id=%s
    """, (student_id, first_name, middle_name, last_name, birthdate, address, contact, program_id, year_level, id))
    conn.commit()
    conn.close()
    return redirect("/admin/students")

# STUDENTS: Delete
@app.route("/admin/students/delete/<int:id>")
def admin_delete_student(id):
    if session.get("role") != "admin":
        return "Access Denied", 403
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM students WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    return redirect("/admin/students")

# PROFILE: view + save
@app.route("/admin/profile", methods=["GET","POST"])
def admin_profile():
    if session.get("role") != "admin":
        return "Access Denied", 403

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        username = request.form["username"]
        password = request.form.get("password")
        # check uniqueness
        cur.execute("SELECT id FROM users WHERE username=%s AND id!=%s", (username, session["user_id"]))
        if cur.fetchone():
            conn.close()
            return "Username already exists", 400

        if password:
            hashed = bcrypt.generate_password_hash(password).decode("utf-8")
            cur.execute("UPDATE users SET username=%s, password=%s WHERE id=%s", (username, hashed, session["user_id"]))
        else:
            cur.execute("UPDATE users SET username=%s WHERE id=%s", (username, session["user_id"]))
        conn.commit()
        # update session username
        session["username"] = username
        conn.close()
        return redirect("/admin/profile")

    # GET
    cur.execute("SELECT id, username FROM users WHERE id=%s", (session["user_id"],))
    user = cur.fetchone()
    conn.close()
    return render_template("admin/profile.html", user=user)

# NOTIFICATIONS: simple example endpoint (could be expanded)
@app.route("/admin/notifications")
def admin_notifications():
    if session.get("role") != "admin":
        return "Access Denied", 403
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, title, message AS msg, DATE_FORMAT(created_at, '%Y-%m-%d %H:%i') AS time, is_read FROM notifications ORDER BY created_at DESC LIMIT 50")
    items = cur.fetchall()
    conn.close()
    return render_template("admin/notifications.html", notifications=items)

# ----------------------------------
# ADMIN - PROGRAM CRUD
# ----------------------------------
@app.route("/admin/programs")
def admin_programs():
    if session.get("role") != "admin":
        return "Access Denied", 403

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM programs ORDER BY name")
    programs = cur.fetchall()
    conn.close()
    return render_template("admin/programs.html", programs=programs)


@app.route("/admin/programs/add", methods=["GET","POST"])
def admin_add_program():
    if session.get("role") != "admin":
        return "Access Denied", 403

    if request.method == "POST":
        code = request.form["code"]
        name = request.form["name"]

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM programs WHERE code=%s OR name=%s", (code, name))
        if cur.fetchone():
            conn.close()
            return "Program code or name already exists!"

        cur.execute("INSERT INTO programs (code, name) VALUES (%s, %s)", (code, name))
        conn.commit()
        conn.close()
        return redirect("/admin/programs")

    return render_template("admin/programs_add.html")


@app.route("/admin/programs/edit/<int:id>", methods=["GET","POST"])
def admin_edit_program(id):
    if session.get("role") != "admin":
        return "Access Denied", 403

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        code = request.form["code"]
        name = request.form["name"]

        cur.execute("SELECT * FROM programs WHERE (code=%s OR name=%s) AND id!=%s", (code, name, id))
        if cur.fetchone():
            conn.close()
            return "Program code or name already exists!"

        cur.execute("UPDATE programs SET code=%s, name=%s WHERE id=%s", (code, name, id))
        conn.commit()
        conn.close()
        return redirect("/admin/programs")

    cur.execute("SELECT * FROM programs WHERE id=%s", (id,))
    program = cur.fetchone()
    conn.close()
    return render_template("admin/programs_edit.html", program=program)


@app.route("/admin/programs/delete/<int:id>")
def admin_delete_program(id):
    if session.get("role") != "admin":
        return "Access Denied", 403

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM programs WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    return redirect("/admin/programs")

# ----------------------------------
# ADMIN - SUBJECT CRUD
# ----------------------------------
@app.route("/admin/subjects")
def admin_subjects():
    if session.get("role") != "admin":
        return "Access Denied", 403

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # Fetch subjects with program names
    cur.execute("""
        SELECT s.*, p.name AS program_name,
               prereq.title AS prereq_title
        FROM subjects s
        LEFT JOIN programs p ON s.program_id = p.id
        LEFT JOIN subjects prereq ON s.prerequisite_id = prereq.id
        ORDER BY s.code
    """)
    subjects = cur.fetchall()
    conn.close()
    return render_template("admin/subjects.html", subjects=subjects)


@app.route("/admin/subjects/add", methods=["GET","POST"])
def admin_add_subject():
    if session.get("role") != "admin":
        return "Access Denied", 403

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # Fetch programs for dropdown
    cur.execute("SELECT id, name FROM programs ORDER BY name")
    programs = cur.fetchall()

    # Fetch all subjects for prerequisite dropdown
    cur.execute("SELECT id, title FROM subjects ORDER BY title")
    all_subjects = cur.fetchall()

    if request.method == "POST":
        code = request.form["code"]
        title = request.form["title"]
        units = request.form["units"]
        program_id = request.form["program_id"]
        year_level = request.form["year_level"]
        semester = request.form["semester"]
        prereq_id = request.form.get("prerequisite_id") or None

        cur.execute("INSERT INTO subjects (code, title, units, program_id, year_level, semester, prerequisite_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (code, title, units, program_id, year_level, semester, prereq_id))
        conn.commit()
        conn.close()
        return redirect("/admin/subjects")

    conn.close()
    return render_template("admin/subjects_add.html", programs=programs, all_subjects=all_subjects)


@app.route("/admin/subjects/edit/<int:id>", methods=["GET","POST"])
def admin_edit_subject(id):
    if session.get("role") != "admin":
        return "Access Denied", 403

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # Fetch programs and subjects for dropdowns
    cur.execute("SELECT id, name FROM programs ORDER BY name")
    programs = cur.fetchall()

    cur.execute("SELECT id, title FROM subjects WHERE id!=%s ORDER BY title", (id,))
    all_subjects = cur.fetchall()

    if request.method == "POST":
        code = request.form["code"]
        title = request.form["title"]
        units = request.form["units"]
        program_id = request.form["program_id"]
        year_level = request.form["year_level"]
        semester = request.form["semester"]
        prereq_id = request.form.get("prerequisite_id") or None

        cur.execute("""
            UPDATE subjects SET code=%s, title=%s, units=%s,
                                program_id=%s, year_level=%s, semester=%s,
                                prerequisite_id=%s WHERE id=%s
        """, (code, title, units, program_id, year_level, semester, prereq_id, id))
        conn.commit()
        conn.close()
        return redirect("/admin/subjects")

    cur.execute("SELECT * FROM subjects WHERE id=%s", (id,))
    subject = cur.fetchone()
    conn.close()
    return render_template("admin/subjects_edit.html", subject=subject, programs=programs, all_subjects=all_subjects)


@app.route("/admin/subjects/delete/<int:id>")
def admin_delete_subject(id):
    if session.get("role") != "admin":
        return "Access Denied", 403

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM subjects WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    return redirect("/admin/subjects")

# ---------------------------
# INSTRUCTOR CRUD
# ---------------------------
@app.route("/admin/instructors")
def admin_instructors():
    if session.get("role") != "admin":
        return "Access Denied", 403

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM instructors ORDER BY last_name, first_name")
    instructors = cur.fetchall()
    conn.close()
    return render_template("admin/instructors.html", instructors=instructors)


@app.route("/admin/instructors/add", methods=["GET","POST"])
def admin_add_instructor():
    if session.get("role") != "admin":
        return "Access Denied", 403

    if request.method=="POST":
        first_name = request.form["first_name"]
        middle_name = request.form.get("middle_name")
        last_name = request.form["last_name"]
        contact = request.form.get("contact")
        email = request.form.get("email")

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO instructors (first_name, middle_name, last_name, contact, email) VALUES (%s,%s,%s,%s,%s)",
            (first_name, middle_name, last_name, contact, email)
        )
        conn.commit()
        conn.close()
        return redirect("/admin/instructors")

    return render_template("admin/instructors_add.html")


@app.route("/admin/instructors/edit/<int:id>", methods=["GET","POST"])
def admin_edit_instructor(id):
    if session.get("role") != "admin":
        return "Access Denied", 403

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if request.method=="POST":
        first_name = request.form["first_name"]
        middle_name = request.form.get("middle_name")
        last_name = request.form["last_name"]
        contact = request.form.get("contact")
        email = request.form.get("email")

        cur.execute(
            "UPDATE instructors SET first_name=%s, middle_name=%s, last_name=%s, contact=%s, email=%s WHERE id=%s",
            (first_name, middle_name, last_name, contact, email, id)
        )
        conn.commit()
        conn.close()
        return redirect("/admin/instructors")

    cur.execute("SELECT * FROM instructors WHERE id=%s", (id,))
    instructor = cur.fetchone()
    conn.close()
    return render_template("admin/instructors_edit.html", instructor=instructor)


@app.route("/admin/instructors/delete/<int:id>")
def admin_delete_instructor(id):
    if session.get("role") != "admin":
        return "Access Denied", 403

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM instructors WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    return redirect("/admin/instructors")

# ---------------------------
# CLASS SCHEDULE CRUD
# ---------------------------
@app.route("/admin/class_schedules")
def admin_class_schedules():
    if session.get("role") != "admin":
        return "Access Denied", 403

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT cs.*, s.title AS subject_title, p.name AS program_name,
               i.first_name, i.last_name
        FROM class_schedules cs
        LEFT JOIN subjects s ON cs.subject_id = s.id
        LEFT JOIN programs p ON s.program_id = p.id
        LEFT JOIN instructors i ON cs.instructor_id = i.id
        ORDER BY cs.semester, cs.day, cs.time_start
    """)
    schedules = cur.fetchall()
    conn.close()
    return render_template("admin/class_schedules.html", schedules=schedules)


@app.route("/admin/class_schedules/add", methods=["GET","POST"])
def admin_add_class_schedule():
    if session.get("role") != "admin":
        return "Access Denied", 403

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # Fetch subjects and instructors for dropdowns
    cur.execute("SELECT id, title FROM subjects ORDER BY title")
    subjects = cur.fetchall()
    cur.execute("SELECT id, first_name, last_name FROM instructors ORDER BY last_name, first_name")
    instructors = cur.fetchall()

    if request.method=="POST":
        subject_id = request.form["subject_id"]
        semester = request.form["semester"]
        day = request.form["day"]
        time_start = request.form["time_start"]
        time_end = request.form["time_end"]
        room = request.form["room"]
        instructor_id = request.form.get("instructor_id") or None
        section = request.form["section"]

        cur.execute("""
            INSERT INTO class_schedules (subject_id, semester, day, time_start, time_end, room, instructor_id, section)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (subject_id, semester, day, time_start, time_end, room, instructor_id, section))
        conn.commit()
        conn.close()
        return redirect("/admin/class_schedules")

    conn.close()
    return render_template("admin/class_schedules_add.html", subjects=subjects, instructors=instructors)


@app.route("/admin/class_schedules/edit/<int:id>", methods=["GET","POST"])
def admin_edit_class_schedule(id):
    if session.get("role") != "admin":
        return "Access Denied", 403

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # Fetch subjects and instructors for dropdowns
    cur.execute("SELECT id, title FROM subjects ORDER BY title")
    subjects = cur.fetchall()
    cur.execute("SELECT id, first_name, last_name FROM instructors ORDER BY last_name, first_name")
    instructors = cur.fetchall()

    if request.method=="POST":
        subject_id = request.form["subject_id"]
        semester = request.form["semester"]
        day = request.form["day"]
        time_start = request.form["time_start"]
        time_end = request.form["time_end"]
        room = request.form["room"]
        instructor_id = request.form.get("instructor_id") or None
        section = request.form["section"]

        cur.execute("""
            UPDATE class_schedules
            SET subject_id=%s, semester=%s, day=%s, time_start=%s, time_end=%s,
                room=%s, instructor_id=%s, section=%s
            WHERE id=%s
        """, (subject_id, semester, day, time_start, time_end, room, instructor_id, section, id))
        conn.commit()
        conn.close()
        return redirect("/admin/class_schedules")

    cur.execute("SELECT * FROM class_schedules WHERE id=%s", (id,))
    schedule = cur.fetchone()
    conn.close()
    return render_template("admin/class_schedules_edit.html", schedule=schedule, subjects=subjects, instructors=instructors)


@app.route("/admin/class_schedules/delete/<int:id>")
def admin_delete_class_schedule(id):
    if session.get("role") != "admin":
        return "Access Denied", 403

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM class_schedules WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    return redirect("/admin/class_schedules")

# ----------------------------------
# LOGOUT
# ----------------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
