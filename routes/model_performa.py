from flask import Blueprint, jsonify
from config import get_db

model_bp = Blueprint('model_performa', __name__)

BULAN = ['Jan','Feb','Mar','Apr','Mei','Jun',
         'Jul','Agu','Sep','Okt','Nov','Des']

def _tanggal_indo(dt, dengan_hari=False):
    if not dt:
        return '-'
    if dengan_hari:
        return f"{dt.day:02d} {BULAN[dt.month-1]} {dt.year}"
    return f"{BULAN[dt.month-1]} {dt.year}"

def _status_label(mape):
    if mape <= 5:
        return 'Baik'
    elif mape <= 10:
        return 'Cukup'
    return 'Perlu Update'

def _build_model_data(cursor, jenis, nama_display):
    cursor.execute(
        "SELECT * FROM model_prediksi WHERE jenis_algoritma = %s ORDER BY trained_at ASC",
        (jenis,)
    )
    rows = cursor.fetchall()
    if not rows:
        return None

    aktif = next((r for r in rows if r['is_aktif'] == 1), rows[-1])

    history = [{
        'versi':   r['versi'],
        'tanggal': _tanggal_indo(r['trained_at']),
        'mape':    float(r['mape']) if r['mape'] is not None else 0.0,
        'rmse':    float(r['rmse']) if r['rmse'] is not None else 0.0,
    } for r in rows]

    mape_aktif = float(aktif['mape']) if aktif['mape'] is not None else 0.0

    return {
        'nama':            nama_display,
        'versi':           aktif['versi'],
        'tanggal_update':  _tanggal_indo(aktif['trained_at'], dengan_hari=True),
        'mse':             float(aktif['mse']) if aktif['mse'] is not None else 0.0,
        'rmse':            float(aktif['rmse']) if aktif['rmse'] is not None else 0.0,
        'mape':            mape_aktif,
        'r2':              float(aktif['r2_score']) if aktif['r2_score'] is not None else 0.0,
        'data_latih':      aktif['jumlah_data_latih'],
        'status':          _status_label(mape_aktif),
        'history':         history,
    }

@model_bp.route('/model-performa', methods=['GET'])
def get_model_performa():
    db = None
    try:
        db     = get_db()
        cursor = db.cursor()

        rlb = _build_model_data(cursor, 'Regresi_Linear_Berganda', 'Regresi Linear Berganda')
        rf  = _build_model_data(cursor, 'Random_Forest', 'Random Forest Regression')

        return jsonify({'success': True, 'data': {'rlb': rlb, 'rf': rf}})
    except Exception as e:
        print(f"MODEL PERFORMA ERROR: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if db:
            try:
                db.close()
            except:
                pass