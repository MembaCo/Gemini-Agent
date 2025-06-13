# database.py
# @author: Memba Co.

import sqlite3
import logging
import config

DB_FILE = config.DATABASE_FILE

def get_db_connection():
    """Veritabanı bağlantısı oluşturur ve döner."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Veritabanı tablolarını (eğer yoksa) oluşturur ve şema güncellemelerini yapar."""
    conn = get_db_connection()
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS managed_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                side TEXT NOT NULL,
                amount REAL NOT NULL,
                entry_price REAL NOT NULL,
                timeframe TEXT NOT NULL,
                leverage REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(managed_positions)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'initial_stop_loss' not in columns:
            cursor.execute('ALTER TABLE managed_positions ADD COLUMN initial_stop_loss REAL')
        if 'initial_amount' not in columns:
             cursor.execute('ALTER TABLE managed_positions ADD COLUMN initial_amount REAL')
        if 'partial_tp_executed' not in columns:
            cursor.execute('ALTER TABLE managed_positions ADD COLUMN partial_tp_executed BOOLEAN DEFAULT 0')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS trade_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                amount REAL NOT NULL,
                entry_price REAL NOT NULL,
                close_price REAL NOT NULL,
                pnl REAL NOT NULL,
                status TEXT NOT NULL,
                opened_at TIMESTAMP,
                closed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        logging.info("Veritabanı tabloları başarıyla kontrol edildi/oluşturuldu.")
    except Exception as e:
        logging.error(f"Veritabanı başlatılırken hata oluştu: {e}")
    finally:
        conn.close()

def add_position(pos: dict):
    """managed_positions tablosuna yeni bir pozisyon ekler."""
    conn = get_db_connection()
    try:
        initial_amount = pos['amount']
        initial_sl = pos['stop_loss']
        conn.execute(
            'INSERT INTO managed_positions (symbol, side, amount, initial_amount, entry_price, timeframe, leverage, stop_loss, take_profit, initial_stop_loss) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (pos['symbol'], pos['side'], pos['amount'], initial_amount, pos['entry_price'], pos['timeframe'], pos['leverage'], pos['stop_loss'], pos['take_profit'], initial_sl)
        )
        conn.commit()
        logging.info(f"VERİTABANI: Yeni pozisyon eklendi -> {pos['symbol']}")
    except sqlite3.IntegrityError:
        logging.error(f"VERİTABANI HATA: {pos['symbol']} için zaten aktif bir pozisyon mevcut.")
    finally:
        conn.close()

def update_position_after_partial_tp(symbol: str, new_amount: float, new_sl: float):
    """Kısmi kâr alındıktan sonra pozisyonu günceller ve durumu işaretler."""
    conn = get_db_connection()
    try:
        conn.execute(
            "UPDATE managed_positions SET amount = ?, stop_loss = ?, partial_tp_executed = 1 WHERE symbol = ?",
            (new_amount, new_sl, symbol)
        )
        conn.commit()
        logging.info(f"VERİTABANI: {symbol} için Kısmi TP sonrası pozisyon güncellendi.")
    except Exception as e:
        logging.error(f"Kısmi TP sonrası veritabanı güncellenirken hata: {e}")
    finally:
        conn.close()

def get_all_positions() -> list[dict]:
    """Tüm aktif pozisyonları veritabanından çeker."""
    conn = get_db_connection()
    try:
        cursor = conn.execute('SELECT * FROM managed_positions')
        positions = [dict(row) for row in cursor.fetchall()]
        return positions
    finally:
        conn.close()

def remove_position(symbol: str) -> dict | None:
    """Bir pozisyonu sembolüne göre aktif tablodan siler ve silinen pozisyonu döndürür."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM managed_positions WHERE symbol = ?", (symbol,))
        pos_to_remove = cursor.fetchone()
        
        if pos_to_remove:
            cursor.execute("DELETE FROM managed_positions WHERE symbol = ?", (symbol,))
            conn.commit()
            logging.info(f"VERİTABANI: Pozisyon silindi -> {symbol}")
            return dict(pos_to_remove)
        return None
    finally:
        conn.close()

def update_position_sl(symbol: str, new_sl: float):
    """Bir pozisyonun sadece stop-loss değerini günceller."""
    conn = get_db_connection()
    try:
        conn.execute("UPDATE managed_positions SET stop_loss = ? WHERE symbol = ?", (new_sl, symbol))
        conn.commit()
        logging.info(f"VERİTABANI: {symbol} için SL güncellendi -> {new_sl}")
    finally:
        conn.close()

def log_trade_to_history(closed_pos: dict, close_price: float, status: str):
    """Kapanan bir işlemi geçmiş tablosuna kaydeder."""
    conn = get_db_connection()
    try:
        pnl = 0
        if closed_pos['side'].lower() == 'buy':
            pnl = (close_price - closed_pos['entry_price']) * closed_pos['amount']
        elif closed_pos['side'].lower() == 'sell':
            pnl = (closed_pos['entry_price'] - close_price) * closed_pos['amount']
        
        conn.execute(
            'INSERT INTO trade_history (symbol, side, amount, entry_price, close_price, pnl, status, opened_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (closed_pos['symbol'], closed_pos['side'], closed_pos['amount'], closed_pos['entry_price'], close_price, pnl, status, closed_pos['created_at'])
        )
        conn.commit()
        logging.info(f"VERİTABANI: İşlem geçmişe kaydedildi -> {closed_pos['symbol']}, PNL: {pnl:.2f} USDT, Durum: {status}")
    except Exception as e:
        logging.error(f"İşlem geçmişi kaydedilirken hata: {e}")
    finally:
        conn.close()
