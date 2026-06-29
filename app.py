import os
import sqlite3
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from main_agent import app as langgraph_agent, build_vector_context

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DB_FILE = "chat_history.db"

def init_db():
    """Create the local database schema if it doesn't exist yet."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Table 1: Store separate chat threads
    cursor.execute('''CREATE TABLE IF NOT EXISTS threads 
                      (id TEXT PRIMARY KEY, title TEXT)''')
    # Table 2: Store individual message records bound to threads
    cursor.execute('''CREATE TABLE IF NOT EXISTS messages 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, thread_id TEXT, role TEXT, content TEXT)''')
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def home():
    """Serves the base workspace workspace layout."""
    return render_template("index.html")

@app.route("/get-threads", methods=["GET"])
def get_threads():
    """Fetches all past conversation chains for the left sidebar display."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM threads ORDER BY rowid DESC")
    rows = cursor.fetchall()
    conn.close()
    
    threads_list = [{"id": r[0], "title": r[1]} for r in rows]
    return jsonify(threads_list)

@app.route("/get-messages/<thread_id>", methods=["GET"])
def get_messages(thread_id):
    """Loads all logs belonging to a clicked sidebar thread."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM messages WHERE thread_id = ?", (thread_id,))
    rows = cursor.fetchall()
    conn.close()
    
    history = [{"role": r[0], "content": r[1]} for r in rows]
    return jsonify(history)

@app.route("/upload-pdf", methods=["POST"])
def upload_pdf():
    """Dynamically parses uploaded PDFs into the local vector pool."""
    if 'pdf_file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files['pdf_file']
    if file.filename == '':
        return jsonify({"error": "Selected file is empty"}), 400

    if file and file.filename.endswith('.pdf'):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        try:
            new_retriever = build_vector_context(filepath)
            if new_retriever is None:
                return jsonify({"error": "Failed to compile document vectors."}), 500
            import main_agent
            main_agent.retriever = new_retriever
            return jsonify({"success": True, "filename": filename})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify({"error": "Invalid file extension."}), 400

@app.route("/ask", methods=["POST"])
def ask_agent():
    """Handles query generation while storing inputs into SQLite."""
    data = request.json
    user_message = data.get("message", "")
    thread_id = data.get("thread_id", "")
    
    if not user_message or not thread_id:
        return jsonify({"error": "Missing message or thread parameter specifications"}), 400

    # 1. Fetch existing thread history from the database to pass to LangGraph
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM messages WHERE thread_id = ?", (thread_id,))
    rows = cursor.fetchall()
    db_history = [{"role": r[0], "content": r[1]} for r in rows]

    # 2. If this is a brand new thread string, register it in the sidebar metadata table
    cursor.execute("SELECT id FROM threads WHERE id = ?", (thread_id,))
    if not cursor.fetchone():
        # Title defaults nicely to the first 30 characters of your initial question
        thread_title = user_message[:30] + "..." if len(user_message) > 30 else user_message
        cursor.execute("INSERT INTO threads (id, title) VALUES (?, ?)", (thread_id, thread_title))
    
    # 3. Log user input into database
    cursor.execute("INSERT INTO messages (thread_id, role, content) VALUES (?, 'user', ?)", (thread_id, user_message))
    conn.commit()

    initial_state = {
        "question": user_message,
        "chat_history": db_history,
        "current_source": "none",
        "context_data": "",
        "answer": "",
        "target_route": "web"
    }
    
    try:
        final_output = langgraph_agent.invoke(initial_state)
        ai_response = final_output.get("answer", "No response extracted.")
        source_used = final_output.get("current_source", "unknown")
        
        # 4. Log AI output response into database
        cursor.execute("INSERT INTO messages (thread_id, role, content) VALUES (?, 'assistant', ?)", (thread_id, ai_response))
        conn.commit()
        conn.close()
        
        return jsonify({"answer": ai_response, "source": source_used})
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
