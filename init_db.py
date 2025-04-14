# SQLite database
import sqlite3

DB_PATH = 'downloads.db'

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS downloads (
                download_id TEXT PRIMARY KEY,
                session_id TEXT,
                url TEXT,
                status TEXT,
                format_type TEXT,
                bitrate_or_res TEXT,
                file_path TEXT,
                created_at TIMESTAMP
            )
        ''')
        conn.commit()

init_db()

    