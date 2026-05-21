from dotenv import load_dotenv
load_dotenv()

import os
import re
import json
import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st
import chromadb
import google.generativeai as genai

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

DB_PATH    = "university.db"
CHROMA_DIR = "chroma_db"          # persisted on disk — visible in your project folder
COLLECTION = "few_shot_examples"
EMB_MODEL  = "models/gemini-embedding-001"

# ── Few-shot examples (question → SQL ground truth) ───────────────────────────

FEW_SHOTS = [
    {
        "question": "Show all students with GPA above 8.5",
        "sql": "SELECT s.name, s.gpa FROM STUDENTS s WHERE s.gpa > 8.5 ORDER BY s.gpa DESC",
    },
    {
        "question": "Which instructor earns the most?",
        "sql": "SELECT name, salary FROM INSTRUCTORS ORDER BY salary DESC LIMIT 1",
    },
    {
        "question": "How many students are in each department?",
        "sql": (
            "SELECT d.name AS department, COUNT(s.student_id) AS student_count "
            "FROM DEPARTMENTS d JOIN STUDENTS s ON d.dept_id = s.dept_id "
            "GROUP BY d.dept_id, d.name ORDER BY student_count DESC"
        ),
    },
    {
        "question": "List students enrolled in Machine Learning with their marks",
        "sql": (
            "SELECT s.name, e.marks, e.grade FROM STUDENTS s "
            "JOIN ENROLLMENTS e ON s.student_id = e.student_id "
            "JOIN COURSES c ON e.course_id = c.course_id "
            "WHERE c.title = 'Machine Learning'"
        ),
    },
    {
        "question": "Show average marks per course sorted by highest first",
        "sql": (
            "SELECT c.title, ROUND(AVG(e.marks), 2) AS avg_marks "
            "FROM COURSES c JOIN ENROLLMENTS e ON c.course_id = e.course_id "
            "GROUP BY c.course_id, c.title ORDER BY avg_marks DESC"
        ),
    },
    {
        "question": "Which courses have 4 credits?",
        "sql": (
            "SELECT c.title, c.credits, d.name AS department "
            "FROM COURSES c JOIN DEPARTMENTS d ON c.dept_id = d.dept_id "
            "WHERE c.credits = 4"
        ),
    },
    {
        "question": "Show students who got an A+ grade",
        "sql": (
            "SELECT s.name, c.title AS course, e.marks "
            "FROM STUDENTS s JOIN ENROLLMENTS e ON s.student_id = e.student_id "
            "JOIN COURSES c ON e.course_id = c.course_id WHERE e.grade = 'A+'"
        ),
    },
    {
        "question": "List all courses taught by Dr. Priya Sharma",
        "sql": (
            "SELECT c.title, c.credits, d.name AS department "
            "FROM COURSES c JOIN INSTRUCTORS i ON c.instructor_id = i.instructor_id "
            "JOIN DEPARTMENTS d ON c.dept_id = d.dept_id "
            "WHERE i.name = 'Dr. Priya Sharma'"
        ),
    },
    {
        "question": "What is the average GPA per department?",
        "sql": (
            "SELECT d.name AS department, ROUND(AVG(s.gpa), 2) AS avg_gpa "
            "FROM DEPARTMENTS d JOIN STUDENTS s ON d.dept_id = s.dept_id "
            "GROUP BY d.dept_id, d.name ORDER BY avg_gpa DESC"
        ),
    },
    {
        "question": "Show the top 3 students by GPA",
        "sql": (
            "SELECT s.name, s.gpa, d.name AS department "
            "FROM STUDENTS s JOIN DEPARTMENTS d ON s.dept_id = d.dept_id "
            "ORDER BY s.gpa DESC LIMIT 3"
        ),
    },
    {
        "question": "How many courses does each department offer?",
        "sql": (
            "SELECT d.name AS department, COUNT(c.course_id) AS course_count "
            "FROM DEPARTMENTS d JOIN COURSES c ON d.dept_id = c.dept_id "
            "GROUP BY d.dept_id, d.name"
        ),
    },
    {
        "question": "Which students enrolled in Fall 2023?",
        "sql": (
            "SELECT DISTINCT s.name, s.email FROM STUDENTS s "
            "JOIN ENROLLMENTS e ON s.student_id = e.student_id "
            "WHERE e.semester = 'Fall 2023'"
        ),
    },
    {
        "question": "Show department budgets from highest to lowest",
        "sql": "SELECT name AS department, budget FROM DEPARTMENTS ORDER BY budget DESC",
    },
    {
        "question": "Which student has the highest marks in any course?",
        "sql": (
            "SELECT s.name, c.title AS course, e.marks "
            "FROM STUDENTS s JOIN ENROLLMENTS e ON s.student_id = e.student_id "
            "JOIN COURSES c ON e.course_id = c.course_id "
            "ORDER BY e.marks DESC LIMIT 1"
        ),
    },
    {
        "question": "List instructors and the number of courses they teach",
        "sql": (
            "SELECT i.name AS instructor, COUNT(c.course_id) AS courses_taught "
            "FROM INSTRUCTORS i LEFT JOIN COURSES c ON i.instructor_id = c.instructor_id "
            "GROUP BY i.instructor_id, i.name ORDER BY courses_taught DESC"
        ),
    },
]

# ── DB init ───────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS DEPARTMENTS (
            dept_id  INTEGER PRIMARY KEY,
            name     TEXT NOT NULL,
            building TEXT,
            budget   REAL
        );
        CREATE TABLE IF NOT EXISTS INSTRUCTORS (
            instructor_id INTEGER PRIMARY KEY,
            name          TEXT NOT NULL,
            dept_id       INTEGER REFERENCES DEPARTMENTS(dept_id),
            salary        REAL,
            email         TEXT
        );
        CREATE TABLE IF NOT EXISTS STUDENTS (
            student_id      INTEGER PRIMARY KEY,
            name            TEXT NOT NULL,
            age             INTEGER,
            email           TEXT,
            dept_id         INTEGER REFERENCES DEPARTMENTS(dept_id),
            enrollment_year INTEGER,
            gpa             REAL
        );
        CREATE TABLE IF NOT EXISTS COURSES (
            course_id     INTEGER PRIMARY KEY,
            title         TEXT NOT NULL,
            dept_id       INTEGER REFERENCES DEPARTMENTS(dept_id),
            credits       INTEGER,
            instructor_id INTEGER REFERENCES INSTRUCTORS(instructor_id)
        );
        CREATE TABLE IF NOT EXISTS ENROLLMENTS (
            enrollment_id INTEGER PRIMARY KEY,
            student_id    INTEGER REFERENCES STUDENTS(student_id),
            course_id     INTEGER REFERENCES COURSES(course_id),
            semester      TEXT,
            grade         TEXT,
            marks         REAL
        );
    """)
    cur.execute("SELECT COUNT(*) FROM DEPARTMENTS")
    if cur.fetchone()[0] == 0:
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
            (1,  'Krish Naik',      22, 'krish@uni.edu',     1, 2022, 8.9),
            (2,  'Sudhanshu Kumar', 23, 'sudhanshu@uni.edu', 2, 2021, 9.1),
            (3,  'Darius Shah',     21, 'darius@uni.edu',    1, 2023, 7.8),
            (4,  'Vikash Gupta',    24, 'vikash@uni.edu',    2, 2020, 8.2),
            (5,  'Dipesh Joshi',    22, 'dipesh@uni.edu',    3, 2022, 7.5),
            (6,  'Ananya Rao',      21, 'ananya@uni.edu',    1, 2023, 9.3),
            (7,  'Rahul Mehra',     25, 'rahul@uni.edu',     4, 2019, 6.8),
            (8,  'Pooja Singh',     22, 'pooja@uni.edu',     2, 2022, 8.7),
            (9,  'Arjun Nair',      23, 'arjun@uni.edu',     1, 2021, 8.0),
            (10, 'Meera Pillai',    20, 'meera@uni.edu',     3, 2024, 9.0),
            (11, 'Saurabh Tiwari',  24, 'saurabh@uni.edu',  4, 2020, 7.2),
            (12, 'Nidhi Agarwal',   21, 'nidhi@uni.edu',    2, 2023, 8.5),
        ])
        cur.executemany("INSERT INTO COURSES VALUES (?,?,?,?,?)", [
            (1, 'Machine Learning',   2, 4, 2),
            (2, 'Database Systems',   1, 3, 3),
            (3, 'Deep Learning',      2, 4, 2),
            (4, 'Algorithms & DS',    1, 3, 1),
            (5, 'Linear Algebra',     3, 3, 4),
            (6, 'Quantum Mechanics',  4, 4, 5),
            (7, 'Python Programming', 1, 3, 1),
            (8, 'Data Visualization', 2, 3, 2),
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

# ── Schema introspection ──────────────────────────────────────────────────────

@st.cache_resource
def get_schema():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    schema = {}
    for t in tables:
        cur.execute(f"PRAGMA table_info({t})")
        schema[t] = [{"name": c[1], "type": c[2]} for c in cur.fetchall()]
    conn.close()
    return schema

def schema_to_text(schema: dict) -> str:
    lines = []
    for table, cols in schema.items():
        col_str = ", ".join(f"{c['name']} {c['type']}" for c in cols)
        lines.append(f"  {table}({col_str})")
    return "\n".join(lines)

# ── SQL safety ────────────────────────────────────────────────────────────────

_UNSAFE = re.compile(
    r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|TRUNCATE|REPLACE|ATTACH|DETACH)\b",
    re.IGNORECASE,
)

def is_safe(sql: str) -> bool:
    return not _UNSAFE.search(sql)

# ── Agent 1 · Table Selector ──────────────────────────────────────────────────

def select_tables(question: str, schema: dict) -> dict:
    """Ask Gemini which tables are needed, return pruned schema."""
    table_summaries = "\n".join(
        f"- {t}: {', '.join(c['name'] for c in cols)}"
        for t, cols in schema.items()
    )
    prompt = f"""You are a database expert. Given these tables:
{table_summaries}

Which tables are needed to answer this question: "{question}"

Respond with ONLY a JSON array of table names. Example: ["STUDENTS", "DEPARTMENTS"]
No explanation, no markdown, no extra text."""

    model = genai.GenerativeModel("gemini-3-flash-preview")
    resp  = model.generate_content(prompt).text.strip()

    # Strip markdown fences if present
    resp = re.sub(r"```(?:json)?", "", resp, flags=re.IGNORECASE).strip().strip("`")

    try:
        selected = json.loads(resp)
        # Keep only valid table names; fall back to full schema if empty
        filtered = {t: schema[t] for t in selected if t in schema}
        return filtered if filtered else schema
    except (json.JSONDecodeError, TypeError):
        return schema  # safe fallback

# ── Agent 2 · RAG Few-Shot Retrieval (ChromaDB) ───────────────────────────────

class GeminiEmbeddingFn(chromadb.EmbeddingFunction):
    """Bridges ChromaDB's embedding interface to Google's Gemini API."""
    def __call__(self, input: chromadb.Documents) -> chromadb.Embeddings:
        return [
            genai.embed_content(
                model=EMB_MODEL,
                content=text,
                task_type="retrieval_document",
            )["embedding"]
            for text in input
        ]

@st.cache_resource
def get_vector_store():
    """
    Persistent ChromaDB collection seeded with few-shot Q→SQL pairs.
    Stored on disk at CHROMA_DIR — visible in your project folder.
    """
    client     = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_or_create_collection(
        name=COLLECTION,
        embedding_function=GeminiEmbeddingFn(),
        metadata={"hnsw:space": "cosine"},
    )
    if collection.count() == 0:
        collection.add(
            ids=[str(i) for i in range(len(FEW_SHOTS))],
            documents=[ex["question"] for ex in FEW_SHOTS],
            metadatas=[{"sql": ex["sql"]}  for ex in FEW_SHOTS],
        )
    return collection

def retrieve_examples(question: str, k: int = 3) -> list[dict]:
    """Query ChromaDB with cosine similarity, return top-k Q→SQL pairs."""
    collection = get_vector_store()
    results    = collection.query(
        query_texts=[question],
        n_results=k,
    )
    return [
        {"question": doc, "sql": meta["sql"]}
        for doc, meta in zip(
            results["documents"][0],
            results["metadatas"][0],
        )
    ]

# ── Agent 3 · SQL Generator ───────────────────────────────────────────────────

def generate_sql(question: str, pruned_schema: dict, examples: list[dict]) -> str:
    """Generate SQL using pruned schema + few-shot examples."""
    schema_text = schema_to_text(pruned_schema)

    shots_text = "\n\n".join(
        f"Q: {ex['question']}\nSQL: {ex['sql']}" for ex in examples
    )

    prompt = f"""You are an expert SQLite query writer.

DATABASE SCHEMA (only the relevant tables):
{schema_text}

SIMILAR EXAMPLES (use these as style reference):
{shots_text}

RULES:
- Output ONLY the raw SQL SELECT query.
- No markdown, no code fences, no explanation.
- Use JOINs when data spans tables.
- Use table aliases to avoid ambiguity.
- Do not end with a semicolon.

Now write the SQL for: {question}"""

    model = genai.GenerativeModel("gemini-3-flash-preview")
    sql   = model.generate_content(prompt).text.strip()
    sql   = re.sub(r"^```(?:sql)?", "", sql, flags=re.IGNORECASE).strip()
    sql   = re.sub(r"```$", "", sql).strip()
    return sql

# ── Query runner ──────────────────────────────────────────────────────────────

def run_query(sql: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df   = pd.read_sql_query(sql, conn)
    conn.close()
    return df

# ── UI helpers ────────────────────────────────────────────────────────────────

EXAMPLES = [
    "Show all students with GPA above 8.5",
    "Which instructor earns the most?",
    "List students enrolled in Machine Learning with their marks",
    "How many students are in each department?",
    "Show average marks per course, sorted highest first",
    "Which courses have 4 credits?",
    "Show students who got an A+ grade",
    "List all courses taught by Dr. Priya Sharma",
]

def render_sidebar(schema: dict):
    with st.sidebar:
        st.markdown("## 🗄️ Schema Explorer")
        for table, cols in schema.items():
            with st.expander(f"📋 {table}  ({len(cols)} cols)"):
                for col in cols:
                    st.markdown(f"- `{col['name']}` &nbsp; *{col['type']}*")
        st.divider()
        st.markdown("**Pipeline**")
        st.markdown(
            "1. 🤖 Table Selector Agent\n"
            "2. 📚 RAG Few-Shot Retrieval\n"
            "3. ⚡ SQL Generator Agent"
        )
        st.divider()
        st.markdown("**Stack**")
        st.markdown("- Google Gemini · Gemini Embeddings\n- SQLite · Pandas · Streamlit")

def render_chart(df: pd.DataFrame):
    numeric = df.select_dtypes(include="number").columns.tolist()
    text    = df.select_dtypes(exclude="number").columns.tolist()
    if len(df) > 1 and numeric and text:
        st.markdown("#### 📊 Auto Visualization")
        st.bar_chart(df.set_index(text[0])[numeric])

# ── Main app ──────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="NL → SQL Explorer",
        page_icon="🎓",
        layout="wide",
    )

    init_db()
    schema = get_schema()
    render_sidebar(schema)

    if "history" not in st.session_state:
        st.session_state.history = []

    st.title("🎓 Natural Language → SQL Explorer")
    st.markdown(
        "Ask a question in plain English. A **3-agent pipeline** — "
        "Table Selector → RAG Few-Shot → SQL Generator — produces and runs the query."
    )

    with st.expander("💡 Example questions"):
        for ex in EXAMPLES:
            st.markdown(f"- *{ex}*")

    st.divider()

    question = st.text_area(
        "Ask anything about the university data:",
        placeholder="e.g.  Show students with GPA above 8.5 and their department",
        height=90,
    )
    run_btn = st.button("🔍 Run Query", type="primary")

    if run_btn:
        q = question.strip()
        if not q:
            st.warning("Please enter a question first.")
            st.stop()

        sql, pruned_schema, examples = None, None, None

        # ── Agent 1: Table Selection ──────────────────────────────────────────
        with st.status("🤖 Agent 1 · Table Selector — picking relevant tables…") as s1:
            try:
                pruned_schema = select_tables(q, schema)
                tables_chosen = list(pruned_schema.keys())
                s1.update(
                    label=f"✅ Agent 1 · Selected {len(tables_chosen)} table(s): `{'`, `'.join(tables_chosen)}`",
                    state="complete",
                )
            except Exception as e:
                pruned_schema = schema
                s1.update(label=f"⚠️ Agent 1 fallback (used full schema): {e}", state="error")

        # ── Agent 2: RAG Few-Shot Retrieval ───────────────────────────────────
        with st.status("📚 Agent 2 · RAG — retrieving similar Q→SQL examples…") as s2:
            try:
                examples = retrieve_examples(q, k=3)
                s2.update(
                    label=f"✅ Agent 2 · Retrieved {len(examples)} similar examples via cosine similarity",
                    state="complete",
                )
            except Exception as e:
                examples = FEW_SHOTS[:3]
                s2.update(label=f"⚠️ Agent 2 fallback (used first 3 examples): {e}", state="error")

        with st.expander("📖 Retrieved few-shot examples"):
            for ex in examples:
                st.markdown(f"**Q:** *{ex['question']}*")
                st.code(ex["sql"], language="sql")

        # ── Agent 3: SQL Generation ───────────────────────────────────────────
        with st.status("⚡ Agent 3 · SQL Generator — writing query…") as s3:
            try:
                sql = generate_sql(q, pruned_schema, examples)
                s3.update(label="✅ Agent 3 · SQL generated", state="complete")
            except Exception as e:
                st.error(f"SQL generation failed: {e}")
                st.stop()

        st.markdown("#### Generated SQL")
        st.code(sql, language="sql")

        if not is_safe(sql):
            st.error("⛔ Query blocked — only SELECT statements are allowed.")
            st.stop()

        # ── Execute ───────────────────────────────────────────────────────────
        try:
            df = run_query(sql)
        except Exception as e:
            st.error(f"SQL execution error: {e}")
            st.stop()

        st.markdown(f"#### Results &nbsp; `{len(df)} row(s) · {len(df.columns)} col(s)`")
        st.dataframe(df, use_container_width=True, hide_index=True)

        csv = df.to_csv(index=False).encode()
        st.download_button("⬇️ Download as CSV", data=csv,
                           file_name="results.csv", mime="text/csv")

        render_chart(df)

        st.session_state.history.append({
            "time":     datetime.now().strftime("%H:%M:%S"),
            "question": q,
            "sql":      sql,
            "tables":   list(pruned_schema.keys()),
            "rows":     len(df),
        })

    # ── Query history ─────────────────────────────────────────────────────────
    if st.session_state.history:
        st.divider()
        with st.expander(f"🕓 Query History  ({len(st.session_state.history)} queries this session)"):
            for entry in reversed(st.session_state.history):
                col_a, col_b, col_c = st.columns([3, 2, 1])
                with col_a:
                    st.markdown(f"**[{entry['time']}]** {entry['question']}")
                with col_b:
                    st.markdown(f"Tables: `{'`, `'.join(entry['tables'])}`")
                with col_c:
                    st.markdown(f"`{entry['rows']} rows`")
                st.code(entry["sql"], language="sql")
                st.divider()

if __name__ == "__main__":
    main()
