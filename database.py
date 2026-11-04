import sqlite3
from pathlib import Path
from config import ADMIN_IDS

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "bot.db"

COURSES_DATA = [
    ("EXIT", "Information Systems Exit Exam Resources", 4, 2),
    ("Gtlr2013", "Global Trends", 2, 1),
    ("Incl2011", "Inclusiveness", 2, 1),
    ("InSy2021", "Introduction to Information Systems and Society", 2, 1),
    ("InSy2061", "System Analysis and Design", 2, 1),
    ("Stat2023", "Introduction to Statistics", 2, 1),
    ("Econs2021", "Economics", 2, 1),
    ("InSy2032", "Basic Computer Programming II", 2, 1),
    ("InSy2042", "Object Oriented Programming", 2, 2),
    ("InSy2044", "Data Structure and Algorithms", 2, 2),
    ("InSy2051", "Operating System", 2, 2),
    ("InSy2071", "Fundamentals of Database Systems", 2, 2),
    ("AcFn2025", "Fundamentals of Accounting", 2, 2),
    ("Mgmt2022", "Introduction to Management", 2, 2),
    ("INSY-3081", "Data Communication and Computer Networks", 3, 1),
    ("INSY-3091", "Digital Marketing", 3, 1),
    ("INSY-3122", "Human Computer Interaction", 3, 1),
    ("INSY-3072", "Advanced Database Systems", 3, 1),
    ("INSY-3092", "Internet Programming", 3, 1),
    ("INSY-3073", "Information Storage and Retrieval", 3, 1),
    ("InSy3062", "Research Methods in Information Systems", 3, 2),
    ("InSy3112", "Information Systems Project Management", 3, 2),
    ("InSy3123", "Mobile Application Development", 3, 2),
    ("InSy3101", "Fundamentals of Artificial Intelligence", 3, 2),
    ("InSy3082", "Systems and Network Administration", 3, 2),
    ("InSy3102", "Knowledge Management", 3, 2),
    ("InSy4133", "Final Year Project I", 4, 1),
    ("InSy4131", "Internship", 4, 1),
    ("InSy4103", "Introduction to Machine Learning", 4, 1),
    ("InSy4083", "Information System Security", 4, 1),
    ("InSy4113", "Information System Strategic Operations and Program Management", 4, 1),
    ("InSy4132", "Seminar in Information System", 4, 2),
]


def get_connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_code TEXT UNIQUE NOT NULL,
                course_title TEXT NOT NULL,
                year INTEGER NOT NULL,
                semester INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                material_type TEXT NOT NULL,
                title TEXT NOT NULL,
                file_id TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_courses_year_sem ON courses(year, semester)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_materials_course_type ON materials(course_id, material_type)")


def seed_courses():
    with get_connection() as conn:
        conn.executemany("""
            INSERT OR IGNORE INTO courses (course_code, course_title, year, semester)
            VALUES (?, ?, ?, ?)
        """, COURSES_DATA)
        
        for aid in ADMIN_IDS:
            conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (aid,))


def get_admin_set():
    with get_connection() as conn:
        rows = conn.execute("SELECT user_id FROM admins").fetchall()
    return {r["user_id"] for r in rows}


def add_admin_db(user_id: int):
    with get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))


def remove_admin_db(user_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM admins WHERE user_id=?", (user_id,))


def get_courses(year, semester):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, course_code, course_title FROM courses WHERE year=? AND semester=? AND course_code != 'EXIT' ORDER BY course_code",
            (year, semester),
        ).fetchall()
    return [(r["id"], r["course_code"], r["course_title"]) for r in rows]


def get_course(course_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT course_code, course_title, year, semester FROM courses WHERE id=?",
            (course_id,),
        ).fetchone()
    return (row["course_code"], row["course_title"], row["year"], row["semester"]) if row else None


def get_course_by_code(code):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, course_code, course_title, year, semester FROM courses WHERE course_code=? COLLATE NOCASE",
            (code.strip(),),
        ).fetchone()
    return (row["id"], row["course_code"], row["course_title"], row["year"], row["semester"]) if row else None


def get_materials(course_id, material_type):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT title, file_id FROM materials WHERE course_id=? AND material_type=? ORDER BY id DESC",
            (course_id, material_type),
        ).fetchall()
    return [(r["title"], r["file_id"]) for r in rows]


def get_materials_with_ids(course_id, material_type):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, title, file_id FROM materials WHERE course_id=? AND material_type=? ORDER BY id DESC",
            (course_id, material_type),
        ).fetchall()
    return [(r["id"], r["title"], r["file_id"]) for r in rows]


def get_all_materials_detailed():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT m.id, c.course_code, m.material_type, m.title 
            FROM materials m
            JOIN courses c ON m.course_id = c.id
            ORDER BY m.id DESC
        """).fetchall()
    return [(r["id"], r["course_code"], r["material_type"], r["title"]) for r in rows]


def delete_material_db(material_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM materials WHERE id=?", (material_id,))


def get_exit_materials():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT m.id, m.title, m.file_id 
            FROM materials m
            JOIN courses c ON m.course_id = c.id
            WHERE c.course_code = 'EXIT' OR m.material_type = 'exit'
            ORDER BY m.id DESC
        """).fetchall()
    return [(r["id"], r["title"], r["file_id"]) for r in rows]


def add_material(course_id, material_type, title, file_id):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO materials (course_id, material_type, title, file_id) VALUES (?, ?, ?, ?)",
            (course_id, material_type, title, file_id),
        )


def get_admin_stats():
    with get_connection() as conn:
        courses = conn.execute("SELECT COUNT(*) FROM courses WHERE course_code != 'EXIT'").fetchone()[0]
        materials = conn.execute("SELECT COUNT(*) FROM materials").fetchone()[0]
        admins = conn.execute("SELECT COUNT(*) FROM admins").fetchone()[0]
    return courses, materials, admins


if __name__ == "__main__":
    init_db()
    seed_courses()
    print("Database initialized and course list seeded.")