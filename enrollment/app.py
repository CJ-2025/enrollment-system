from flask import Flask, render_template, request, redirect, url_for, session
from flask_bcrypt import Bcrypt
import mysql.connector
from db import get_db_connection

app = Flask(__name__)
app.secret_key = "secretkey123"
bcrypt = Bcrypt(app)

# ----------------------------------
# INDEX (Choose Role)
# ----------------------------------
@app.route("/")
def index():
    return render_template("index.html")

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
            session["role"] = user["role"]
            session["username"] = user["username"]

            # If student, fetch the linked student_id
            if user["role"] == "student":
                cur.execute("SELECT id FROM students WHERE user_id = %s", (user["id"],))
                student = cur.fetchone()
                if student:
                    session["student_id"] = student["id"]
                return redirect("/student/dashboard")

            if user["role"] == "admin":
                return redirect("/admin/dashboard")
            if user["role"] == "registrar":
                return redirect("/registrar/dashboard")
            if user["role"] == "cashier":
                return redirect("/cashier/dashboard")

        return "Invalid username or password"

    return render_template("login.html")

# ----------------------------------
# REGISTRATION PAGE
# ----------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        first_name = request.form.get("first_name", "")
        middle_name = request.form.get("middle_name", "")
        last_name = request.form.get("last_name", "")
        role = "student"  # force student only

        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        # Check for existing username
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        if cur.fetchone():
            return "Username already exists!"

        # Insert user
        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
            (username, hashed_pw, role)
        )
        user_id = cur.lastrowid  # new user ID

        # Insert student record linked to the user
        cur.execute(
            "INSERT INTO students (user_id, first_name, middle_name, last_name) VALUES (%s, %s, %s, %s)",
            (user_id, first_name, middle_name, last_name)
        )
        conn.commit()
        conn.close()

        return redirect("/login")

    return render_template("register.html")

# ADMIN CREATES OTHER ROLES
@app.route("/admin/create-user", methods=["GET", "POST"])
def admin_create_user():
    if "role" not in session or session["role"] != "admin":
        return "Access Denied"

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        role = request.form["role"]

        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        if cur.fetchone():
            return "Username already exists!"

        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
            (username, hashed_pw, role)
        )
        conn.commit()

        return redirect("/admin/dashboard")

    return render_template("create_user.html")


# ----------------------------------
# admin DASHBOARDS
# ----------------------------------
@app.route("/admin/dashboard")
def admin_dashboard():
    return render_template("dashboard_admin.html")

# List Programs
@app.route("/admin/programs")
def admin_programs():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM programs")
    programs = cur.fetchall()
    return render_template("programs.html", programs=programs)

# Add Program
@app.route("/admin/programs/add", methods=["GET","POST"])
def add_program():
    if request.method=="POST":
        code = request.form["code"]
        name = request.form["name"]
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO programs (code,name) VALUES (%s,%s)", (code,name))
        conn.commit()
        return redirect("/admin/programs")
    return render_template("programs_add.html")

# Edit Program
@app.route("/admin/programs/edit/<int:id>", methods=["GET","POST"])
def edit_program(id):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    if request.method=="POST":
        code = request.form["code"]
        name = request.form["name"]
        cur.execute("UPDATE programs SET code=%s, name=%s WHERE id=%s", (code,name,id))
        conn.commit()
        return redirect("/admin/programs")
    cur.execute("SELECT * FROM programs WHERE id=%s",(id,))
    program = cur.fetchone()
    return render_template("programs_edit.html", program=program)

# Delete Program
@app.route("/admin/programs/delete/<int:id>")
def delete_program(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM programs WHERE id=%s", (id,))
    conn.commit()
    return redirect("/admin/programs")

# --------------------------------------
# SUBJECTS CRUD
# --------------------------------------

@app.route("/admin/subjects")
def admin_subjects():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT s.*, p.name AS program_name 
        FROM subjects s
        JOIN programs p ON s.program_id = p.id
    """)
    subjects = cur.fetchall()
    return render_template("subjects.html", subjects=subjects)

@app.route("/admin/subjects/add", methods=["GET","POST"])
def add_subject():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM programs")
    programs = cur.fetchall()

    if request.method=="POST":
        code = request.form["code"]
        title = request.form["title"]
        units = request.form["units"]
        program_id = request.form["program_id"]
        year_level = request.form["year_level"]
        prerequisite_id = request.form.get("prerequisite_id") or None

        cur.execute("""
            INSERT INTO subjects 
            (code,title,units,program_id,year_level,prerequisite_id)
            VALUES (%s,%s,%s,%s,%s,%s)
        """,(code,title,units,program_id,year_level,prerequisite_id))
        conn.commit()
        return redirect("/admin/subjects")

    # For prerequisite dropdown
    cur.execute("SELECT * FROM subjects")
    all_subjects = cur.fetchall()
    return render_template("subjects_add.html", programs=programs, all_subjects=all_subjects)

@app.route("/admin/subjects/edit/<int:id>", methods=["GET","POST"])
def edit_subject(id):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    if request.method=="POST":
        code = request.form["code"]
        title = request.form["title"]
        units = request.form["units"]
        program_id = request.form["program_id"]
        year_level = request.form["year_level"]
        prerequisite_id = request.form.get("prerequisite_id") or None
        cur.execute("""
            UPDATE subjects
            SET code=%s,title=%s,units=%s,program_id=%s,year_level=%s,prerequisite_id=%s
            WHERE id=%s
        """,(code,title,units,program_id,year_level,prerequisite_id,id))
        conn.commit()
        return redirect("/admin/subjects")

    cur.execute("SELECT * FROM subjects WHERE id=%s", (id,))
    subject = cur.fetchone()
    cur.execute("SELECT * FROM programs")
    programs = cur.fetchall()
    cur.execute("SELECT * FROM subjects")
    all_subjects = cur.fetchall()
    return render_template("subjects_edit.html", subject=subject, programs=programs, all_subjects=all_subjects)

@app.route("/admin/subjects/delete/<int:id>")
def delete_subject(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM subjects WHERE id=%s", (id,))
    conn.commit()
    return redirect("/admin/subjects")
# List Users
@app.route("/admin/users")
def admin_users():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    
    roles = ["student", "admin", "registrar", "cashier"]
    users_by_role = {}
    
    for role in roles:
        if role == "student":
            cur.execute("""
                SELECT u.id, u.username, u.role, s.first_name, s.middle_name, s.last_name
                FROM users u
                LEFT JOIN students s ON u.id = s.user_id
                WHERE u.role = %s
            """, (role,))
        else:
            cur.execute("SELECT * FROM users WHERE role = %s", (role,))
        users_by_role[role] = cur.fetchall()
    
    conn.close()
    return render_template("users.html", users_by_role=users_by_role)



@app.route("/admin/users/add", methods=["GET","POST"])
def admin_add_user():
    role = request.args.get("role", "student")  # default to student

    if request.method=="POST":
        username = request.form["username"]
        password = request.form["password"]
        role = request.form.get("role", role)  # use hidden input if needed
        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        # Insert user
        cur.execute("INSERT INTO users (username,password,role) VALUES (%s,%s,%s)",(username,hashed_pw,role))
        user_id = cur.lastrowid

        # If student, also add a student record
        if role == "student":
            first_name = request.form.get("first_name","")
            middle_name = request.form.get("middle_name","")
            last_name = request.form.get("last_name","")
            cur.execute(
                "INSERT INTO students (user_id, first_name, middle_name, last_name) VALUES (%s,%s,%s,%s)",
                (user_id, first_name, middle_name, last_name)
            )

        conn.commit()
        conn.close()
        return redirect("/admin/users")

    return render_template("users_add.html", role=role)

# Delete User
@app.route("/admin/users/delete/<int:id>")
def admin_delete_user(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id=%s",(id,))
    conn.commit()
    return redirect("/admin/users")

# List Class Schedules
@app.route("/admin/class-schedules")
def admin_class_schedules():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT cs.*, s.code AS subject_code, s.title AS subject_title, p.name AS program_name
        FROM class_schedules cs
        JOIN subjects s ON cs.subject_id = s.id
        JOIN programs p ON s.program_id = p.id
        ORDER BY s.code, cs.semester, cs.day
    """)
    schedules = cur.fetchall()
    conn.close()
    return render_template("class_schedules.html", schedules=schedules)

# Add Class Schedule
@app.route("/admin/class-schedules/add", methods=["GET","POST"])
def add_class_schedule():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM subjects")
    subjects = cur.fetchall()

    if request.method == "POST":
        subject_id = request.form["subject_id"]
        semester = request.form["semester"]
        day = request.form["day"]
        time_start = request.form["time_start"]
        time_end = request.form["time_end"]
        room = request.form.get("room","")
        instructor = request.form.get("instructor","")

        cur.execute("""
            INSERT INTO class_schedules 
            (subject_id, semester, day, time_start, time_end, room, instructor)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (subject_id, semester, day, time_start, time_end, room, instructor))
        conn.commit()
        conn.close()
        return redirect("/admin/class-schedules")

    conn.close()
    return render_template("class_schedule_add.html", subjects=subjects)

# Edit Class Schedule
@app.route("/admin/class-schedules/edit/<int:id>", methods=["GET","POST"])
def edit_class_schedule(id):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM subjects")
    subjects = cur.fetchall()

    cur.execute("SELECT * FROM class_schedules WHERE id=%s", (id,))
    schedule = cur.fetchone()

    if request.method == "POST":
        subject_id = request.form["subject_id"]
        semester = request.form["semester"]
        day = request.form["day"]
        time_start = request.form["time_start"]
        time_end = request.form["time_end"]
        room = request.form.get("room","")
        instructor = request.form.get("instructor","")

        cur.execute("""
            UPDATE class_schedules
            SET subject_id=%s, semester=%s, day=%s, time_start=%s, time_end=%s, room=%s, instructor=%s
            WHERE id=%s
        """, (subject_id, semester, day, time_start, time_end, room, instructor, id))
        conn.commit()
        conn.close()
        return redirect("/admin/class-schedules")

    conn.close()
    return render_template("class_schedule_edit.html", subjects=subjects, schedule=schedule)

# Delete Class Schedule
@app.route("/admin/class-schedules/delete/<int:id>")
def delete_class_schedule(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM class_schedules WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    return redirect("/admin/class-schedules")


# ----------------------------------
# DASHBOARDS
# ----------------------------------


@app.route("/registrar/enrollments")
def registrar_enrollments():
    if session.get("role") != "registrar":
        return redirect("/login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT e.id as enrollment_id, s.first_name, s.last_name, e.semester, e.school_year, e.status
        FROM enrollments e
        JOIN students s ON e.student_id = s.id
        WHERE e.status='pending'
    """)
    enrollments = cur.fetchall()
    conn.close()
    return render_template("registrar_enrollments.html", enrollments=enrollments)

@app.route("/registrar/enrollments/validate/<int:enroll_id>/<string:action>")
def validate_enrollment(enroll_id, action):
    if session.get("role") != "registrar":
        return redirect("/login")

    status = "approved" if action == "approve" else "rejected"

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE enrollments SET status=%s WHERE id=%s", (status, enroll_id))
    conn.commit()
    conn.close()
    return redirect("/registrar/enrollments")

# Approve Enrollment

@app.route("/cashier/dashboard")
def cashier_dashboard():
    return render_template("dashboard_cashier.html")

# ----------------------------------
# STUDENT DASHBOARD & ENROLLMENT   
# ----------------------------------

@app.route("/student/dashboard")
def student_dashboard():
    if session.get("role") != "student":
        return redirect("/login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT s.*, p.name AS program_name
        FROM students s
        LEFT JOIN programs p ON s.program_id = p.id
        WHERE s.id = %s
    """, (session["student_id"],))
    
    student = cur.fetchone()
    conn.close()

    return render_template("student_dashboard.html", student=student, title="Student Dashboard")


# ---------------- ENROLLMENT PAGE ---------------- #

@app.route("/student/enroll", methods=["GET", "POST"])
def student_enroll():
    if session.get("role") != "student":
        return redirect("/login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # Fetch programs for student to pick
    cur.execute("SELECT * FROM programs")
    programs = cur.fetchall()

    # If student selected a program
    if request.method == "POST":
        program_id = request.form["program_id"]
        year_level = request.form["year_level"]
        semester = request.form["semester"]
        school_year = request.form["school_year"]
        selected_subjects = request.form.getlist("subjects")

        # Save selected program for student (optional)
        cur.execute("UPDATE students SET program_id=%s, year_level=%s WHERE id=%s",
                    (program_id, year_level, session["student_id"]))

        # Create enrollment (status = pending)
        cur.execute("""
            INSERT INTO enrollments (student_id, semester, school_year, status)
            VALUES (%s, %s, %s, 'pending')
        """, (session["student_id"], semester, school_year))
        enrollment_id = cur.lastrowid

        # Save chosen subjects
        for sid in selected_subjects:
            cur.execute("""
                INSERT INTO enrollment_subjects (enrollment_id, subject_id)
                VALUES (%s, %s)
            """, (enrollment_id, sid))

        conn.commit()
        conn.close()
        return "Enrollment submitted and pending approval!"

    conn.close()
    return render_template("student_enroll.html", programs=programs)



# ---------------- VIEW ENROLLED SUBJECTS ---------------- #
@app.route("/student/enroll", methods=["GET", "POST"])
def student_enrolled():
    if session.get("role") != "student":
        return redirect("/login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # Fetch programs for dropdown
    cur.execute("SELECT * FROM programs")
    programs = cur.fetchall()

    if request.method == "POST":
        program_id = request.form.get("program_id")
        year_level = request.form.get("year_level")
        semester = request.form.get("semester")
        school_year = request.form.get("school_year")  # safer: .get() instead of ["school_year"]
        selected_subjects = request.form.getlist("subjects")

        if not (program_id and year_level and semester and school_year):
            conn.close()
            return "Please fill in all required fields!", 400

        # Save student program/year
        cur.execute(
            "UPDATE students SET program_id=%s, year_level=%s WHERE id=%s",
            (program_id, year_level, session["student_id"])
        )

        # Create enrollment
        cur.execute("""
            INSERT INTO enrollments (student_id, semester, school_year, status)
            VALUES (%s,%s,%s,'pending')
        """, (session["student_id"], semester, school_year))
        enrollment_id = cur.lastrowid

        # Save subjects
        for sid in selected_subjects:
            cur.execute("""
                INSERT INTO enrollment_subjects (enrollment_id, subject_id)
                VALUES (%s,%s)
            """, (enrollment_id, sid))

        conn.commit()
        conn.close()
        return "Enrollment submitted successfully!"

    conn.close()
    return render_template("student_enroll.html", programs=programs)


# ----------------------------------
# ADMIN – STUDENT CRUD
# ----------------------------------

@app.route("/students")
def students():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM students")
    data = cur.fetchall()
    return render_template("students.html", students=data)

@app.route("/students/add", methods=["GET", "POST"])
def add_student():
    if request.method == "POST":
        first = request.form["first_name"]
        middle = request.form["middle_name"]
        last = request.form["last_name"]

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO students (first_name,middle_name,last_name) VALUES (%s,%s,%s)",
            (first, middle, last)
        )
        conn.commit()
        return redirect("/students")

    return render_template("add_student.html")

@app.route("/students/edit/<int:id>", methods=["GET", "POST"])
def edit_student(id):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        first = request.form["first_name"]
        middle = request.form["middle_name"]
        last = request.form["last_name"]

        cur.execute(
            "UPDATE students SET first_name=%s, middle_name=%s, last_name=%s WHERE id=%s",
            (first, middle, last, id)
        )
        conn.commit()
        return redirect("/students")

    cur.execute("SELECT * FROM students WHERE id = %s", (id,))
    student = cur.fetchone()
    return render_template("edit_student.html", student=student)

# ----------------------------------
# LOGOUT
# ----------------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
