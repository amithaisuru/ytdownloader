import datetime
import os
import sqlite3
import threading

from init_db import DB_PATH

db_lock = threading.Lock()

def cleanup_expired_sessions():
    expiration = datetime.datetime.now() - datetime.timedelta(seconds=30)
    with db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                'SELECT session_id, file_path FROM downloads WHERE created_at < ?',
                (expiration,)
            )
            sessions_to_delete = set()
            for row in cursor.fetchall():
                session_id, file_path = row
                sessions_to_delete.add(session_id)
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
            for session_id in sessions_to_delete:
                session_dir = os.path.join('downloads', session_id)
                if os.path.exists(session_dir):
                    import shutil
                    try:
                        shutil.rmtree(session_dir)
                    except Exception:
                        pass
            conn.execute('DELETE FROM downloads WHERE created_at < ?', (expiration,))
            conn.commit()

    # Also check flask_session folder for expired sessions
    import glob
    session_dir = 'flask_session'
    if os.path.exists(session_dir):
        for session_file in glob.glob(os.path.join(session_dir, 'sess_*')):
            try:
                file_mtime = os.path.getmtime(session_file)
                if (datetime.datetime.now() - datetime.datetime.fromtimestamp(file_mtime)).total_seconds() > 30:
                    session_id = None
                    with open(session_file, 'rb') as f:
                        import pickle
                        data = pickle.load(f)
                        session_id = data.get('session_id')
                    os.remove(session_file)
                    if session_id:
                        session_dir = os.path.join('downloads', session_id)
                        if os.path.exists(session_dir):
                            import shutil
                            shutil.rmtree(session_dir)
            except Exception:
                pass