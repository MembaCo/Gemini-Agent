# dashboard/app.py
# @author: Memba Co.

import sqlite3
import os
import logging
import sys
import secrets
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
from flask_socketio import SocketIO
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from contextlib import contextmanager
from functools import wraps
from dotenv import load_dotenv

# --- Proje Kök Dizinini Ayarla ve .env Yükle ---
APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if APP_ROOT not in sys.path:
    sys.path.append(APP_ROOT)
dotenv_path = os.path.join(APP_ROOT, '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- Çekirdek modülleri yükle ---
import core
import config
import tools
import database

# --- Uygulama ve Eklentileri Başlat ---
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(16))
limiter = Limiter(get_remote_address, app=app, default_limits=["200 per day", "50 per hour"])
socketio = SocketIO(app, async_mode='gevent')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
DATABASE_PATH = os.path.join(APP_ROOT, config.DATABASE_FILE)

# --- Veritabanı Bağlantısı ve Yardımcı Fonksiyonlar ---
@contextmanager
def get_db_connection():
    if not os.path.exists(DATABASE_PATH):
        raise FileNotFoundError(f"Veritabanı bulunamadı: {DATABASE_PATH}")
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Ana Rotalar ---
@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if 'logged_in' in session: return redirect(url_for('index'))
    if request.method == 'POST':
        if request.form.get('password') == os.getenv('DASHBOARD_PASSWORD'):
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            flash('Geçersiz şifre.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('Başarıyla çıkış yaptınız.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html')

# --- SocketIO Olayları (Real-time İletişim) ---
@socketio.on('connect')
@login_required
def handle_connect(auth):
    """İstemci bağlandığında tetiklenir."""
    logging.info(f"İstemci bağlandı: {request.sid}")
    emit_dashboard_data()

@socketio.on('disconnect')
def handle_disconnect():
    """İstemci bağlantısı kesildiğinde tetiklenir."""
    logging.info(f"İstemci bağlantısı kesildi: {request.sid}")

@socketio.on('request_dashboard_data')
@login_required
def handle_data_request():
    emit_dashboard_data()

@socketio.on('start_scan')
@login_required
def handle_start_scan():
    logging.info("Web arayüzünden proaktif tarama başlatma isteği alındı.")

    def status_callback(message):
        socketio.emit('scan_status', {'message': message})
        socketio.sleep(0)

    def opportunity_callback(opportunity_data):
        if config.WEB_AUTO_CONFIRM_OPPORTUNITY:
            status_callback(f"Otomatik onay aktif. {opportunity_data['symbol']} için pozisyon açılıyor...")
            result = core.open_new_position(
                opportunity_data['recommendation'],
                opportunity_data['symbol'],
                opportunity_data['current_price'],
                opportunity_data['timeframe']
            )
            socketio.emit('toast', {'message': result['message'], 'type': result['status']})
            emit_dashboard_data()
        else:
            status_callback(f"Onay bekleniyor: {opportunity_data['symbol']}")
            socketio.emit('new_opportunity', opportunity_data)

    socketio.start_background_task(
        core.run_proactive_scanner,
        opportunity_callback=opportunity_callback,
        status_callback=status_callback
    )

@socketio.on('confirm_trade')
@login_required
def handle_confirm_trade(data):
    if not data: return
    result = core.open_new_position(
        data.get('recommendation'),
        data.get('symbol'),
        data.get('current_price'),
        data.get('timeframe')
    )
    socketio.emit('toast', {'message': result.get('message'), 'type': result.get('status')})
    if result.get('status') == 'success':
        emit_dashboard_data()

@socketio.on('reanalyze_position')
@login_required
def handle_reanalyze_position(data):
    """Bir pozisyon için yeniden analiz isteğini alır ve işler."""
    symbol = data.get('symbol')
    if not symbol:
        socketio.emit('toast', {'message': 'Yeniden analiz için sembol belirtilmedi.', 'type': 'error'})
        return

    position = next((p for p in database.get_all_positions() if p['symbol'] == symbol), None)
    if not position:
        socketio.emit('toast', {'message': f'{symbol} için yönetilen pozisyon bulunamadı.', 'type': 'error'})
        return
    
    socketio.emit('toast', {'message': f'{symbol} yeniden analiz ediliyor...', 'type': 'info'})
    
    analysis_result = core.reanalyze_position(position)
    
    if analysis_result.get('status') == 'success':
        analysis_result['data']['symbol'] = symbol
    
    socketio.emit('reanalysis_result', analysis_result)


# --- API Endpoints (Real-time olmayan işlemler için) ---
@app.route('/api/close-position', methods=['POST'])
@login_required
def api_close_position():
    symbol = request.get_json().get('symbol')
    if not symbol: return jsonify({"status": "error", "message": "Sembol belirtilmedi."}), 400
    result = core.close_position_by_symbol(symbol, "WEB_MANUAL")
    if result.get('status') == 'success':
        emit_dashboard_data()
    return jsonify(result)

@app.route('/api/new-analysis', methods=['POST'])
@login_required
def api_new_analysis():
    data = request.get_json()
    symbol, timeframe = data.get('symbol'), data.get('timeframe', '15m')
    if not symbol: return jsonify({"status": "error", "message": "Sembol belirtilmedi."}), 400
    
    analysis_result = core.perform_analysis(symbol, timeframe)
    if analysis_result.get('status') != 'success': return jsonify(analysis_result)
        
    if analysis_result.get('recommendation') not in ['AL', 'SAT']:
        return jsonify({"status": "info", "message": f"Net sinyal yok: {analysis_result.get('recommendation')}", "data": analysis_result})

    position_result = core.open_new_position(
        analysis_result['recommendation'],
        analysis_result['symbol'],
        analysis_result['current_price'],
        analysis_result['timeframe']
    )
    if position_result.get('status') == 'success':
        emit_dashboard_data()
    return jsonify(position_result)


# --- Yardımcı Fonksiyonlar ---
def emit_dashboard_data():
    """Veritabanı ve borsadan verileri alıp istemciye gönderir."""
    try:
        with get_db_connection() as conn:
            db_positions = conn.execute('SELECT * FROM managed_positions ORDER BY created_at DESC').fetchall()
            trade_history = conn.execute('SELECT * FROM trade_history ORDER BY closed_at DESC').fetchall()

        exchange_positions = tools.get_open_positions_from_exchange.invoke({})
        
        exchange_pnl_map = {
            tools._get_unified_symbol(pos.get('symbol')): float(pos.get('unrealizedPnl', 0.0)) 
            for pos in exchange_positions if pos.get('symbol')
        }
        
        open_positions_with_pnl = []
        for pos in db_positions:
            pos_dict = dict(pos)
            pos_dict['unrealizedPnl'] = exchange_pnl_map.get(pos_dict['symbol'], 0.0)
            open_positions_with_pnl.append(pos_dict)

        total_pnl = sum(trade['pnl'] for trade in trade_history)
        winning_trades = sum(1 for trade in trade_history if trade['pnl'] > 0)
        total_trades = len(trade_history)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        stats = {'total_pnl': f"{total_pnl:,.2f}", 'win_rate': f"{win_rate:.2f}", 'total_trades': total_trades}
        pnl_timeline = [{'x': t['closed_at'], 'y': sum(trade['pnl'] for trade in trade_history if trade['closed_at'] <= t['closed_at'])} for t in sorted(trade_history, key=lambda x: x['closed_at'])]
        
        socketio.emit('dashboard_data', {
            "stats": stats, 
            "open_positions": open_positions_with_pnl, 
            "trade_history": [dict(row) for row in trade_history], 
            "pnl_timeline": pnl_timeline
        })
    except Exception as e:
        logging.error(f"Dashboard verisi gönderilirken hata: {e}", exc_info=True)
        socketio.emit('toast', {'message': f'Dashboard verileri alınamadı: {e}', 'type': 'error'})

if __name__ == '__main__':
    try:
        logging.info("Dashboard için borsa bağlantısı kuruluyor...")
        tools.initialize_exchange(config.DEFAULT_MARKET_TYPE)
        host = '0.0.0.0'
        port = 5001
        logging.info(f"Dashboard sunucusu http://{host}:{port} adresinde başlatılıyor...")
        socketio.run(app, host=host, port=port, debug=False)
    except Exception as e:
        logging.critical(f"Dashboard başlatılamadı: {e}", exc_info=True)