import sqlite3

conn = sqlite3.connect("university.db")
cur = conn.cursor()

cur.executescript("""
    DROP TABLE IF EXISTS ENROLLMENTS;
    DROP TABLE IF EXISTS COURSES;
    DROP TABLE IF EXISTS STUDENTS;
    DROP TABLE IF EXISTS INSTRUCTORS;
    DROP TABLE IF EXISTS DEPARTMENTS;

    CREATE TABLE DEPARTMENTS (
        dept_id  INTEGER PRIMARY KEY,
        name     TEXT NOT NULL,
        building TEXT,
        budget   REAL
    );

    CREATE TABLE INSTRUCTORS (
        instructor_id INTEGER PRIMARY KEY,
        name          TEXT NOT NULL,
        dept_id       INTEGER REFERENCES DEPARTMENTS(dept_id),
        salary        REAL,
        email         TEXT
    );

    CREATE TABLE STUDENTS (
        student_id      INTEGER PRIMARY KEY,
        name            TEXT NOT NULL,
        age             INTEGER,
        email           TEXT,
        dept_id         INTEGER REFERENCES DEPARTMENTS(dept_id),
        enrollment_year INTEGER,
        gpa             REAL
    );

    CREATE TABLE COURSES (
        course_id     INTEGER PRIMARY KEY,
        title         TEXT NOT NULL,
        dept_id       INTEGER REFERENCES DEPARTMENTS(dept_id),
        credits       INTEGER,
        instructor_id INTEGER REFERENCES INSTRUCTORS(instructor_id)
    );

    CREATE TABLE ENROLLMENTS (
        enrollment_id INTEGER PRIMARY KEY,
        student_id    INTEGER REFERENCES STUDENTS(student_id),
        course_id     INTEGER REFERENCES COURSES(course_id),
        semester      TEXT,
        grade         TEXT,
        marks         REAL
    );
""")

cur.executemany("INSERT INTO DEPARTMENTS VALUES (?,?,?,?)", [
    (1, 'Computer Science', 'Tech Block A', 500000),
    (2, 'Data Science',     'Tech Block B', 450000),
    (3, 'Mathematics',      'Science Wing', 300000),
    (4, 'Physics',          'Science Wing', 350000),
])

cur.executemany("INSERT INTO INSTRUCTORS VALUES (?,?,?,?,?)", [
    (1, 'Dr. Rajesh Kumar',  1, 95000, 'rajesh@uni.edu'),
    (2, 'Dr. Priya Sharma',  2, 88000, 'priya@uni.edu'),
    (3, 'Dr. Amit Verma',    1, 92000, 'amit@uni.edu'),
    (4, 'Dr. Sneha Patel',   3, 78000, 'sneha@uni.edu'),
    (5, 'Dr. Vikram Singh',  4, 82000, 'vikram@uni.edu'),
])

cur.executemany("INSERT INTO STUDENTS VALUES (?,?,?,?,?,?,?)", [
    (1,  'Krish Naik',       22, 'krish@uni.edu',      1, 2022, 8.9),
    (2,  'Sudhanshu Kumar',  23, 'sudhanshu@uni.edu',  2, 2021, 9.1),
    (3,  'Darius Shah',      21, 'darius@uni.edu',     1, 2023, 7.8),
    (4,  'Vikash Gupta',     24, 'vikash@uni.edu',     2, 2020, 8.2),
    (5,  'Dipesh Joshi',     22, 'dipesh@uni.edu',     3, 2022, 7.5),
    (6,  'Ananya Rao',       21, 'ananya@uni.edu',     1, 2023, 9.3),
    (7,  'Rahul Mehra',      25, 'rahul@uni.edu',      4, 2019, 6.8),
    (8,  'Pooja Singh',      22, 'pooja@uni.edu',      2, 2022, 8.7),
    (9,  'Arjun Nair',       23, 'arjun@uni.edu',      1, 2021, 8.0),
    (10, 'Meera Pillai',     20, 'meera@uni.edu',      3, 2024, 9.0),
    (11, 'Saurabh Tiwari',   24, 'saurabh@uni.edu',   4, 2020, 7.2),
    (12, 'Nidhi Agarwal',    21, 'nidhi@uni.edu',      2, 2023, 8.5),
])

cur.executemany("INSERT INTO COURSES VALUES (?,?,?,?,?)", [
    (1, 'Machine Learning',     2, 4, 2),
    (2, 'Database Systems',     1, 3, 3),
    (3, 'Deep Learning',        2, 4, 2),
    (4, 'Algorithms & DS',      1, 3, 1),
    (5, 'Linear Algebra',       3, 3, 4),
    (6, 'Quantum Mechanics',    4, 4, 5),
    (7, 'Python Programming',   1, 3, 1),
    (8, 'Data Visualization',   2, 3, 2),
])

cur.executemany("INSERT INTO ENROLLMENTS VALUES (?,?,?,?,?,?)", [
    (1,  1,  1, 'Spring 2024', 'A',  92),
    (2,  1,  2, 'Spring 2024', 'B+', 87),
    (3,  2,  1, 'Spring 2024', 'A+', 98),
    (4,  2,  3, 'Fall 2023',   'A',  91),
    (5,  3,  7, 'Spring 2024', 'B',  78),
    (6,  3,  4, 'Spring 2024', 'C+', 65),
    (7,  4,  8, 'Fall 2023',   'A',  90),
    (8,  5,  5, 'Spring 2024', 'B+', 85),
    (9,  6,  1, 'Spring 2024', 'A+', 97),
    (10, 6,  2, 'Fall 2023',   'A',  93),
    (11, 7,  6, 'Spring 2024', 'C',  60),
    (12, 8,  3, 'Spring 2024', 'A',  94),
    (13, 8,  8, 'Fall 2023',   'B+', 88),
    (14, 9,  4, 'Spring 2024', 'B',  80),
    (15, 10, 5, 'Spring 2024', 'A+', 99),
    (16, 11, 6, 'Fall 2023',   'B',  75),
    (17, 12, 1, 'Spring 2024', 'A',  95),
    (18, 12, 8, 'Spring 2024', 'A+', 96),
    (19, 1,  4, 'Fall 2023',   'A',  91),
    (20, 4,  1, 'Spring 2024', 'B+', 86),
])

conn.commit()
conn.close()
print("university.db created with 5 tables and sample data.")
