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
            session["user_id"] = user["id"]

            # If student, fetch the linked student_id
            if user["role"] == "student":
                cur.execute("SELECT id FROM students WHERE user_id = %s", (user["id"],))
                student = cur.fetchone()
                if student:
                    session["student_id"] = student["id"]
                conn.close()
                return redirect("/student/dashboard")

            conn.close()
            if user["role"] == "admin":
                return redirect("/admin/dashboard")
            if user["role"] == "registrar":
                return redirect("/registrar/dashboard")
            if user["role"] == "cashier":
                return redirect("/cashier/dashboard")

        conn.close()
        return "Invalid username or password"

    return render_template("login.html")

# ----------------------------------
# REGISTRATION PAGE - REMOVED (Admin only creates users)
# ----------------------------------
# Public registration is disabled - only admin can create accounts

# ----------------------------------
# ADMIN DASHBOARD
# ----------------------------------
@app.route("/admin/dashboard")
def admin_dashboard():
    if "role" not in session or session["role"] != "admin":
        return "Access Denied", 403
    return render_template("dashboard_admin.html")

# ----------------------------------
# ADMIN - USER CRUD
# ----------------------------------

# List Users
@app.route("/admin/users")
def admin_users():
    if "role" not in session or session["role"] != "admin":
        return "Access Denied", 403
        
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    
    roles = ["student", "admin", "registrar", "cashier"]
    users_by_role = {}
    
    for role in roles:
        if role == "student":
            cur.execute("""
                SELECT u.id, u.username, u.role, s.id as student_id, s.first_name, s.middle_name, s.last_name
                FROM users u
                LEFT JOIN students s ON u.id = s.user_id
                WHERE u.role = %s
            """, (role,))
        else:
            cur.execute("SELECT * FROM users WHERE role = %s", (role,))
        users_by_role[role] = cur.fetchall()
    
    conn.close()
    return render_template("User Account and Role Management/users.html", users_by_role=users_by_role)

# Add User (Admin Only)
@app.route("/admin/users/add", methods=["GET","POST"])
def admin_add_user():
    if "role" not in session or session["role"] != "admin":
        return "Access Denied", 403
        
    role = request.args.get("role", "student")

    if request.method=="POST":
        username = request.form["username"]
        password = request.form["password"]
        role = request.form.get("role", role)
        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        # Check if username exists
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        if cur.fetchone():
            conn.close()
            return "Username already exists!"

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

    return render_template("User Account and Role Management/users_add.html", role=role)

# Edit User
@app.route("/admin/users/edit/<int:id>", methods=["GET","POST"])
def admin_edit_user(id):
    if "role" not in session or session["role"] != "admin":
        return "Access Denied", 403
        
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    
    if request.method=="POST":
        username = request.form["username"]
        password = request.form.get("password")
        role = request.form["role"]
        
        # Check if username exists for other users
        cur.execute("SELECT * FROM users WHERE username=%s AND id!=%s", (username, id))
        if cur.fetchone():
            conn.close()
            return "Username already exists!"
        
        # Update user
        if password:
            hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
            cur.execute("UPDATE users SET username=%s, password=%s, role=%s WHERE id=%s",
                       (username, hashed_pw, role, id))
        else:
            cur.execute("UPDATE users SET username=%s, role=%s WHERE id=%s",
                       (username, role, id))
        
        # If student, update student info
        if role == "student":
            first_name = request.form.get("first_name","")
            middle_name = request.form.get("middle_name","")
            last_name = request.form.get("last_name","")
            cur.execute("""
                UPDATE students 
                SET first_name=%s, middle_name=%s, last_name=%s 
                WHERE user_id=%s
            """, (first_name, middle_name, last_name, id))
        
        conn.commit()
        conn.close()
        return redirect("/admin/users")
    
    # GET request
    cur.execute("SELECT * FROM users WHERE id=%s", (id,))
    user = cur.fetchone()
    
    student = None
    if user and user["role"] == "student":
        cur.execute("SELECT * FROM students WHERE user_id=%s", (id,))
        student = cur.fetchone()
    
    conn.close()
    return render_template("User Account and Role Management/users_edit.html", user=user, student=student)

# Delete User
@app.route("/admin/users/delete/<int:id>")
def admin_delete_user(id):
    if "role" not in session or session["role"] != "admin":
        return "Access Denied", 403
        
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Delete student record if exists
    cur.execute("DELETE FROM students WHERE user_id=%s",(id,))
    # Delete user
    cur.execute("DELETE FROM users WHERE id=%s",(id,))
    
    conn.commit()
    conn.close()
    return redirect("/admin/users")

# ----------------------------------
# ADMIN - STUDENT CRUD
# ----------------------------------

@app.route("/admin/students")
def admin_students():
    if "role" not in session or session["role"] != "admin":
        return "Access Denied", 403
        
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT s.*, p.name AS program_name, u.username
        FROM students s
        LEFT JOIN programs p ON s.program_id = p.id
        LEFT JOIN users u ON s.user_id = u.id
    """)
    data = cur.fetchall()
    conn.close()
    return render_template("Student Registration/students.html", students=data)

@app.route("/admin/students/add", methods=["GET", "POST"])
def add_student():
    if "role" not in session or session["role"] != "admin":
        return "Access Denied", 403
        
    if request.method == "POST":
        first = request.form["first_name"]
        middle = request.form["middle_name"]
        last = request.form["last_name"]
        program_id = request.form.get("program_id") or None
        year_level = request.form.get("year_level") or None

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO students (first_name,middle_name,last_name,program_id,year_level) VALUES (%s,%s,%s,%s,%s)",
            (first, middle, last, program_id, year_level)
        )
        conn.commit()
        conn.close()
        return redirect("/admin/students")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM programs")
    programs = cur.fetchall()
    conn.close()
    return render_template("Student Registration/add_student.html", programs=programs)

@app.route("/admin/students/edit/<int:id>", methods=["GET", "POST"])
def edit_student(id):
    if "role" not in session or session["role"] != "admin":
        return "Access Denied", 403
        
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        first = request.form["first_name"]
        middle = request.form["middle_name"]
        last = request.form["last_name"]
        program_id = request.form.get("program_id") or None
        year_level = request.form.get("year_level") or None

        cur.execute(
            "UPDATE students SET first_name=%s, middle_name=%s, last_name=%s, program_id=%s, year_level=%s WHERE id=%s",
            (first, middle, last, program_id, year_level, id)
        )
        conn.commit()
        conn.close()
        return redirect("/admin/students")

    cur.execute("SELECT * FROM students WHERE id = %s", (id,))
    student = cur.fetchone()
    cur.execute("SELECT * FROM programs")
    programs = cur.fetchall()
    conn.close()
    return render_template("Student Registration/edit_student.html", student=student, programs=programs)

@app.route("/admin/students/delete/<int:id>")
def delete_student(id):
    if "role" not in session or session["role"] != "admin":
        return "Access Denied", 403
        
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM students WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    return redirect("/admin/students")

# ----------------------------------
# ADMIN - PROGRAM CRUD
# ----------------------------------

@app.route("/admin/programs")
def admin_programs():
    if "role" not in session or session["role"] != "admin":
        return "Access Denied", 403
        
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM programs")
    programs = cur.fetchall()
    conn.close()
    return render_template("Subject and Curriculum Management/programs.html", programs=programs)

@app.route("/admin/programs/add", methods=["GET","POST"])
def add_program():
    if "role" not in session or session["role"] != "admin":
        return "Access Denied", 403
        
    if request.method=="POST":
        code = request.form["code"]
        name = request.form["name"]
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO programs (code,name) VALUES (%s,%s)", (code,name))
        conn.commit()
        conn.close()
        return redirect("/admin/programs")
    return render_template("Subject and Curriculum Management/programs_add.html")

@app.route("/admin/programs/edit/<int:id>", methods=["GET","POST"])
def edit_program(id):
    if "role" not in session or session["role"] != "admin":
        return "Access Denied", 403
        
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    if request.method=="POST":
        code = request.form["code"]
        name = request.form["name"]
        cur.execute("UPDATE programs SET code=%s, name=%s WHERE id=%s", (code,name,id))
        conn.commit()
        conn.close()
        return redirect("/admin/programs")
    cur.execute("SELECT * FROM programs WHERE id=%s",(id,))
    program = cur.fetchone()
    conn.close()
    return render_template("Subject and Curriculum Management/programs_edit.html", program=program)

@app.route("/admin/programs/delete/<int:id>")
def delete_program(id):
    if "role" not in session or session["role"] != "admin":
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
    if "role" not in session or session["role"] != "admin":
        return "Access Denied", 403
        
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT s.*, p.name AS program_name 
        FROM subjects s
        JOIN programs p ON s.program_id = p.id
    """)
    subjects = cur.fetchall()
    conn.close()
    return render_template("Subject and Curriculum Management/subjects.html", subjects=subjects)

@app.route("/admin/subjects/add", methods=["GET","POST"])
def add_subject():
    if "role" not in session or session["role"] != "admin":
        return "Access Denied", 403
        
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
        conn.close()
        return redirect("/admin/subjects")

    cur.execute("SELECT * FROM subjects")
    all_subjects = cur.fetchall()
    conn.close()
    return render_template("Subject and Curriculum Management/subjects_add.html", programs=programs, all_subjects=all_subjects)

@app.route("/admin/subjects/edit/<int:id>", methods=["GET","POST"])
def edit_subject(id):
    if "role" not in session or session["role"] != "admin":
        return "Access Denied", 403
        
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
        conn.close()
        return redirect("/admin/subjects")

    cur.execute("SELECT * FROM subjects WHERE id=%s", (id,))
    subject = cur.fetchone()
    cur.execute("SELECT * FROM programs")
    programs = cur.fetchall()
    cur.execute("SELECT * FROM subjects")
    all_subjects = cur.fetchall()
    conn.close()
    return render_template("Subject and Curriculum Management/subjects_edit.html", subject=subject, programs=programs, all_subjects=all_subjects)

@app.route("/admin/subjects/delete/<int:id>")
def delete_subject(id):
    if "role" not in session or session["role"] != "admin":
        return "Access Denied", 403
        
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM subjects WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    return redirect("/admin/subjects")

# ----------------------------------
# ADMIN - CLASS SCHEDULE CRUD
# ----------------------------------

@app.route("/admin/schedules")
def admin_schedules():
    if "role" not in session or session["role"] != "admin":
        return "Access Denied", 403
        
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT cs.*, s.code as subject_code, s.title as subject_title
        FROM class_schedules cs
        JOIN subjects s ON cs.subject_id = s.id
        ORDER BY cs.day, cs.time_start
    """)
    schedules = cur.fetchall()
    conn.close()
    return render_template("Class Scheduling/schedules.html", schedules=schedules)

@app.route("/admin/schedules/add", methods=["GET","POST"])
def add_schedule():
    if "role" not in session or session["role"] != "admin":
        return "Access Denied", 403
        
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if request.method=="POST":
        subject_id = request.form["subject_id"]
        section = request.form["section"]
        day = request.form["day"]
        time_start = request.form["time_start"]
        time_end = request.form["time_end"]
        room = request.form["room"]
        instructor = request.form["instructor"]

        cur.execute("""
            INSERT INTO class_schedules 
            (subject_id, section, day, time_start, time_end, room, instructor)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (subject_id, section, day, time_start, time_end, room, instructor))
        conn.commit()
        conn.close()
        return redirect("/admin/schedules")

    cur.execute("SELECT * FROM subjects")
    subjects = cur.fetchall()
    conn.close()
    return render_template("Class Scheduling/schedules_add.html", subjects=subjects)

@app.route("/admin/schedules/edit/<int:id>", methods=["GET","POST"])
def edit_schedule(id):
    if "role" not in session or session["role"] != "admin":
        return "Access Denied", 403
        
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if request.method=="POST":
        subject_id = request.form["subject_id"]
        section = request.form["section"]
        day = request.form["day"]
        time_start = request.form["time_start"]
        time_end = request.form["time_end"]
        room = request.form["room"]
        instructor = request.form["instructor"]

        cur.execute("""
            UPDATE class_schedules 
            SET subject_id=%s, section=%s, day=%s, time_start=%s, 
                time_end=%s, room=%s, instructor=%s
            WHERE id=%s
        """, (subject_id, section, day, time_start, time_end, room, instructor, id))
        conn.commit()
        conn.close()
        return redirect("/admin/schedules")

    cur.execute("SELECT * FROM class_schedules WHERE id=%s", (id,))
    schedule = cur.fetchone()
    cur.execute("SELECT * FROM subjects")
    subjects = cur.fetchall()
    conn.close()
    return render_template("Class Scheduling/schedules_edit.html", schedule=schedule, subjects=subjects)

@app.route("/admin/schedules/delete/<int:id>")
def delete_schedule(id):
    if "role" not in session or session["role"] != "admin":
        return "Access Denied", 403
        
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM class_schedules WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    return redirect("/admin/schedules")

# ----------------------------------
# REGISTRAR ROUTES
# ----------------------------------

@app.route("/registrar/dashboard")
def registrar_dashboard():
    if "role" not in session or session["role"] != "registrar":
        return "Access Denied", 403
    return render_template("dashboard_registrar.html")

@app.route("/registrar/enrollments")
def registrar_enrollments():
    if session.get("role") != "registrar":
        return "Access Denied", 403

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
    return render_template("enrollment/registrar_enrollments.html", enrollments=enrollments)

@app.route("/registrar/enrollments/validate/<int:enroll_id>/<string:action>")
def validate_enrollment(enroll_id, action):
    if session.get("role") != "registrar":
        return "Access Denied", 403

    status = "approved" if action == "approve" else "rejected"

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE enrollments SET status=%s WHERE id=%s", (status, enroll_id))
    conn.commit()
    conn.close()
    return redirect("/registrar/enrollments")

# ----------------------------------
# CASHIER ROUTES
# ----------------------------------

@app.route("/cashier/dashboard")
def cashier_dashboard():
    if "role" not in session or session["role"] != "cashier":
        return "Access Denied", 403
    return render_template("dashboard_cashier.html")

# ----------------------------------
# STUDENT ROUTES
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

@app.route("/student/enroll", methods=["GET", "POST"])
def student_enroll():
    if session.get("role") != "student":
        return redirect("/login")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT * FROM programs")
    programs = cur.fetchall()

    if request.method == "POST":
        program_id = request.form["program_id"]
        year_level = request.form["year_level"]
        semester = request.form["semester"]
        school_year = request.form["school_year"]
        selected_subjects = request.form.getlist("subjects")

        cur.execute("UPDATE students SET program_id=%s, year_level=%s WHERE id=%s",
                    (program_id, year_level, session["student_id"]))

        cur.execute("""
            INSERT INTO enrollments (student_id, semester, school_year, status)
            VALUES (%s, %s, %s, 'pending')
        """, (session["student_id"], semester, school_year))
        enrollment_id = cur.lastrowid

        for sid in selected_subjects:
            cur.execute("""
                INSERT INTO enrollment_subjects (enrollment_id, subject_id)
                VALUES (%s, %s)
            """, (enrollment_id, sid))

        conn.commit()
        conn.close()
        return "Enrollment submitted and pending approval!"

    conn.close()
    return render_template("enrollment/student_enroll.html", programs=programs)

# ----------------------------------
# LOGOUT
# ----------------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)