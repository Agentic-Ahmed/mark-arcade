from flask import Flask, render_template, request, send_file, jsonify
import os
import sqlite3
import subprocess
import time
import threading

app = Flask(__name__)

# Check if running on Vercel
IS_VERCEL = "VERCEL" in os.environ

DOWNLOAD_FOLDER = '/tmp/downloads' if IS_VERCEL else 'downloads'
DB_PATH = '/tmp/scores.db' if IS_VERCEL else 'scores.db'
ENGINES_FOLDER = 'engines'

# Ensure directories exist
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)
if not os.path.exists(ENGINES_FOLDER):
    os.makedirs(ENGINES_FOLDER)

# Database Setup
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS scores 
                        (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                         game TEXT, 
                         player TEXT, 
                         score INTEGER, 
                         date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

init_db()

# --- Chess Engine Management ---
active_engines = {}

def get_engine_process(engine_name):
    """Starts or retrieves an active engine process."""
    if engine_name in active_engines:
        proc = active_engines[engine_name]
        if proc.poll() is None:
            return proc
        else:
            del active_engines[engine_name]
    
    engine_path = os.path.join(ENGINES_FOLDER, engine_name)
    if not os.path.exists(engine_path):
        return None

    try:
        # Start process with pipes
        proc = subprocess.Popen(
            [engine_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
        active_engines[engine_name] = proc
        return proc
    except Exception as e:
        print(f"Error starting engine {engine_name}: {e}")
        return None

def send_command(proc, command):
    """Sends a UCI command to the engine."""
    if proc.poll() is None:
        try:
            proc.stdin.write(command + "\n")
            proc.stdin.flush()
        except IOError:
            pass

def read_best_move(proc, timeout=5):
    """Reads output until 'bestmove' is found."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        line = proc.stdout.readline().strip()
        if line.startswith("bestmove"):
            return line.split()[1]
    return None

@app.route('/api/chess/engines')
def list_engines():
    """Lists available engine executables."""
    files = [f for f in os.listdir(ENGINES_FOLDER) if f.endswith('.exe') or '.' not in f]
    return jsonify(files)

@app.route('/api/chess/move', methods=['POST'])
def chess_move():
    data = request.json
    fen = data.get('fen')
    engine_name = data.get('engine')
    difficulty = data.get('difficulty', 1) # 1=Easy, 2=Med, 3=Hard

    if not engine_name:
        return jsonify({"error": "No engine selected"}), 400

    proc = get_engine_process(engine_name)
    if not proc:
        return jsonify({"error": "Engine failed to start"}), 500

    # Map difficulty to UCI options and limits
    # Stockfish 'Skill Level' ranges from 0 (weakest) to 20 (strongest)
    skill_level = 20
    limits = "movetime 1000"

    if difficulty == 1:
        skill_level = 0
        limits = "depth 1"
    elif difficulty == 2:
        skill_level = 10
        limits = "depth 5"
    elif difficulty == 3:
        skill_level = 20
        limits = "movetime 1000"
    
    try:
        send_command(proc, "uci")
        send_command(proc, f"setoption name Skill Level value {skill_level}")
        send_command(proc, "isready") # Ensure options are applied
        send_command(proc, f"position fen {fen}")
        send_command(proc, f"go {limits}")
        
        best_move = read_best_move(proc, timeout=10)
        
        if best_move:
            return jsonify({"move": best_move})
        else:
            return jsonify({"error": "Engine timed out"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Routes ---
@app.route('/')
def hub():
    return render_template('hub.html')

@app.route('/game/snake')
def snake():
    return render_template('snake.html')

@app.route('/game/pong')
def pong():
    return render_template('pong.html')

@app.route('/game/tetris')
def tetris():
    return render_template('tetris.html')

@app.route('/game/chess')
def chess():
    return render_template('chess.html')

@app.route('/game/guess')
def guess():
    return render_template('guess.html')

@app.route('/game/checkers')
def checkers():
    return render_template('checkers.html')

@app.route('/game/hockey')
def hockey():
    # Render static version if on Vercel to avoid potential issues
    return render_template('hockey.html')

@app.route('/game/tic-tac-toe')
def tic_tac_toe():
    return render_template('tic-tac-toe.html')

# Vercel needs the 'app' object
# Ensure directories exist
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)
if not os.path.exists(ENGINES_FOLDER):
    os.makedirs(ENGINES_FOLDER)

init_db()

@app.route('/leaderboard')
def leaderboard_page():
    return render_template('leaderboard.html')

@app.route('/api/score', methods=['POST'])
def save_score():
    data = request.json
    game = data.get('game')
    player = data.get('player', 'Anonymous')
    score = data.get('score')
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('INSERT INTO scores (game, player, score) VALUES (?, ?, ?)', (game, player, score))
    return jsonify({"status": "success"})

@app.route('/api/leaderboard/<game>')
def leaderboard(game):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('SELECT player, score, date FROM scores WHERE game = ? ORDER BY score DESC LIMIT 10', (game,))
        scores = [{"player": r[0], "score": r[1], "date": r[2]} for r in cursor.fetchall()]
    return jsonify(scores)

@app.route('/api/leaderboard/all')
def leaderboard_all():
    with sqlite3.connect(DB_PATH) as conn:
        # Get list of all games
        games_cursor = conn.execute('SELECT DISTINCT game FROM scores')
        games = [r[0] for r in games_cursor.fetchall()]
        
        all_scores = {}
        for game in games:
            cursor = conn.execute('SELECT player, score, date FROM scores WHERE game = ? ORDER BY score DESC LIMIT 5', (game,))
            all_scores[game] = [{"player": r[0], "score": r[1], "date": r[2]} for r in cursor.fetchall()]
            
    return jsonify(all_scores)



if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Arcade Hub on port {port}...")
    app.run(host='0.0.0.0', port=port)
