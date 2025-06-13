# dashboard/app.py
# @author: Memba Co.

import sqlite3
import os
from flask import Flask, jsonify, render_template
from flask_cors import CORS
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'trades.db')

def get_db_connection():
    """Veritabanı bağlantısı oluşturur ve döner."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.OperationalError as e:
        print(f"Veritabanı bağlantı hatası: {e}")
        print(f"Aranan dosya yolu: {os.path.abspath(DB_PATH)}")
        return None

@app.route('/')
def index():
    """Ana dashboard sayfasını (index.html) sunar."""
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    """Veritabanından tüm verileri çeker, işler ve JSON formatında döner."""
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Veritabanı bağlantısı kurulamadı."}), 500

    try:
        active_positions = [dict(row) for row in conn.execute('SELECT * FROM managed_positions ORDER BY created_at DESC').fetchall()]
        trade_history = [dict(row) for row in conn.execute('SELECT * FROM trade_history ORDER BY closed_at ASC').fetchall()]

        total_pnl = sum(item['pnl'] for item in trade_history)
        total_trades = len(trade_history)
        winning_trades = sum(1 for item in trade_history if item['pnl'] > 0)
        losing_trades = total_trades - winning_trades
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        best_trade = max(trade_history, key=lambda x: x['pnl'], default={'pnl': 0})
        worst_trade = min(trade_history, key=lambda x: x['pnl'], default={'pnl': 0})

        cumulative_pnl = 0
        chart_points = []
        
        if trade_history:
             first_trade_date = datetime.strptime(trade_history[0]['closed_at'].split('.')[0], '%Y-%m-%d %H:%M:%S')
             start_date = first_trade_date - timedelta(days=1)
             chart_points.append({'x': start_date.strftime('%Y-%m-%d'), 'y': 0})

        for trade in trade_history:
            cumulative_pnl += trade['pnl']
            chart_points.append({
                'x': trade['closed_at'].split(' ')[0],
                'y': cumulative_pnl
            })
        
        chart_data = {"points": chart_points}

        stats = {
            "total_pnl": total_pnl,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "best_trade_pnl": best_trade['pnl'],
            "worst_trade_pnl": worst_trade['pnl']
        }

        response_data = {
            "stats": stats,
            "active_positions": active_positions,
            "trade_history": trade_history,
            "chart_data": chart_data
        }

        return jsonify(response_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    print("Dashboard sunucusu başlatılıyor...")
    print("Panoya erişmek için tarayıcınızda http://127.0.0.1:5001 adresini açın.")
    app.run(host='0.0.0.0', port=5001, debug=False)
