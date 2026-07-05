from flask import Blueprint, request, jsonify
from config import get_db
import joblib
import numpy as np
import os
from datetime import datetime

prediksi_bp = Blueprint('prediksi', __name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', 'models_saved')

def load_models():
    try:
        rlb      = joblib.load(os.path.join(MODEL_DIR, 'model_rlb.pkl'))
        rf       = joblib.load(os.path.join(MODEL_DIR, 'model_rf.pkl'))
        scaler_r = joblib.load(os.path.join(MODEL_DIR, 'scaler_rlb.pkl'))
        scaler_f = joblib.load(os.path.join(MODEL_DIR, 'scaler_rf.pkl'))
        return rlb, rf, scaler_r, scaler_f
    except Exception as e:
        print(f"Error load model: {e}")
        return None, None, None, None


STANDAR_BERAT = {
    1: 25,  2: 27,  3: 30,  4: 33,  5: 36,
    6: 39,  7: 43,  8: 47,  9: 51,  10: 55,
    11: 60, 12: 65, 13: 70, 14: 75, 15: 81,
    16: 87, 17: 93, 18: 99, 19: 106, 20: 113,
    21: 120, 22: 129, 23: 138, 24: 147, 25: 156,
    26: 165, 27: 174, 28: 180, 29: 189, 30: 198,
    31: 207, 32: 216, 33: 225, 34: 234, 35: 255,
    36: 265, 37: 275, 38: 285, 39: 295, 40: 305,
    41: 315, 42: 335, 43: 346, 44: 357, 45: 368,
    46: 379, 47: 390, 48: 401, 49: 420, 50: 435,
    51: 450, 52: 465, 53: 480, 54: 495, 55: 510,
    56: 525, 57: 540, 58: 555, 59: 578, 60: 600,
}

STANDAR_PAKAN = {
    1: 4,   2: 4,   3: 5,   4: 5,   5: 6,
    6: 6,   7: 7,   8: 7,   9: 8,   10: 9,
    11: 9,  12: 10, 13: 11, 14: 12, 15: 13,
    16: 13, 17: 14, 18: 15, 19: 15, 20: 16,
    21: 16, 22: 17, 23: 18, 24: 19, 25: 20,
    26: 21, 27: 21, 28: 22, 29: 23, 30: 24,
    31: 25, 32: 26, 33: 27, 34: 27, 35: 28,
    36: 29, 37: 30, 38: 31, 39: 32, 40: 33,
    41: 33, 42: 34, 43: 35, 44: 36, 45: 37,
    46: 37, 47: 38, 48: 39, 49: 38, 50: 39,
    51: 39, 52: 40, 53: 40, 54: 40, 55: 40,
    56: 40, 57: 41, 58: 41, 59: 41, 60: 42,
}

def get_standar_berat(hari):
    closest = min(STANDAR_BERAT.keys(), key=lambda x: abs(x - hari))
    return STANDAR_BERAT[closest]

def get_standar_pakan(hari):
    closest = min(STANDAR_PAKAN.keys(), key=lambda x: abs(x - hari))
    return STANDAR_PAKAN[closest]


@prediksi_bp.route('/prediksi', methods=['POST'])
def prediksi():
    data = request.get_json()
    try:
        hari         = int(data.get('hari'))
        populasi     = int(data.get('populasi'))
        mortalitas   = int(data.get('mortalitas', 0))
        berat_rata   = float(data.get('berat_rata'))
        peternak_id  = int(data.get('peternak_id', 1))
        nama_batch   = data.get('nama_batch', 'Batch')
        tanggal      = data.get('tanggal', '')
    except (TypeError, ValueError) as e:
        return jsonify({'success': False, 'message': f'Data input tidak valid: {e}'}), 400

    fase           = 'Starter' if hari <= 21 else 'Finisher'
    populasi_akhir = max(populasi - mortalitas, 0)
    berat_standar  = get_standar_berat(hari)
    selisih_berat  = berat_rata - berat_standar

    deviasi_persen_check = (selisih_berat / berat_standar) * 100 if berat_standar else 0
    if deviasi_persen_check < -20:
        status_nutrisi = 'Peringatan_Kritis'
    elif deviasi_persen_check < -10:
        status_nutrisi = 'Peringatan_Ringan'
    else:
        status_nutrisi = 'Normal'

    rlb, rf, scaler_r, scaler_f = load_models()
    if not all([rlb, rf, scaler_r, scaler_f]):
        return jsonify({'success': False, 'message': 'Model tidak tersedia'}), 500

    input_rlb = np.array([[hari, populasi, mortalitas, 0, berat_rata, 0]])
    input_rf  = np.array([[hari, populasi, mortalitas, berat_rata, 0]])

    try:
        x_rlb              = scaler_r.transform(input_rlb)
        x_rf               = scaler_f.transform(input_rf)
        prediksi_pakan_raw = float(rlb.predict(x_rlb)[0])
        estimasi_berat_raw = float(rf.predict(x_rf)[0])
        print(f"[MODEL RAW] pakan={prediksi_pakan_raw:.2f}, berat={estimasi_berat_raw:.2f}")
    except Exception as e:
        print(f"Model prediction error: {e}")
        return jsonify({'success': False, 'message': 'Prediksi gagal'}), 500

    # ── HYBRID CALIBRATION ────────────────────────────────
    standar_pakan_hari_ini = get_standar_pakan(hari)
    pakan_standar_total    = round((standar_pakan_hari_ini * populasi) / 1000, 2)

    batas_bawah_pakan = round(pakan_standar_total * 0.90, 2)
    batas_atas_pakan  = round(pakan_standar_total * 1.10, 2)

    if prediksi_pakan_raw > 0:
        kontribusi_model = prediksi_pakan_raw * 0.05
        variasi = kontribusi_model - (pakan_standar_total * 0.05)
        variasi_clamped = max(-pakan_standar_total * 0.10,
                              min(pakan_standar_total * 0.10, variasi))
        total_pakan_rlb = round(pakan_standar_total + variasi_clamped, 2)
    else:
        total_pakan_rlb = pakan_standar_total

    total_pakan_rlb = round(
        max(batas_bawah_pakan, min(batas_atas_pakan, total_pakan_rlb)), 2
    )
    print(f"[CALIBRATED PAKAN] standar={pakan_standar_total:.2f}kg, "
          f"model_raw={prediksi_pakan_raw:.2f}kg, hasil={total_pakan_rlb:.2f}kg")

    rasio_pertumbuhan   = berat_rata / berat_standar if berat_standar > 0 else 1.0
    berat_panen_standar = round(600.0 * rasio_pertumbuhan, 2)

    if estimasi_berat_raw > 0:
        selisih_model = estimasi_berat_raw - berat_panen_standar
        variasi_berat = selisih_model * 0.05
        variasi_berat_clamped = max(-berat_panen_standar * 0.05,
                                    min(berat_panen_standar * 0.05, variasi_berat))
        berat_panen_est = round(berat_panen_standar + variasi_berat_clamped, 2)
    else:
        berat_panen_est = berat_panen_standar

    berat_panen_est = max(berat_panen_est, berat_rata)
    print(f"[CALIBRATED BERAT] rasio={rasio_pertumbuhan:.3f}, "
          f"standar_panen={berat_panen_standar:.2f}g, hasil={berat_panen_est:.2f}g")

    pakan_kumulatif_gram = sum(get_standar_pakan(h) for h in range(1, hari + 1))
    if berat_rata > 0:
        fcr_estimasi = round(pakan_kumulatif_gram / berat_rata, 2)
        fcr_estimasi = max(3.0, min(5.5, fcr_estimasi))
    else:
        fcr_estimasi = 4.0
    print(f"[FCR] kumulatif_pakan={pakan_kumulatif_gram}g, "
          f"berat={berat_rata}g, FCR={fcr_estimasi}")
    # ─────────────────────────────────────────────────────

    populasi_panen = populasi_akhir
    total_bobot    = round((berat_panen_est / 1000) * populasi_panen, 2)
    deviasi_persen = round((selisih_berat / berat_standar) * 100, 2) if berat_standar else 0.0
    tanggal_input  = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    tanggal_date   = datetime.now().date()

    db = None
    try:
        db     = get_db()
        cursor = db.cursor()

        # Ambil id model yang sedang aktif dari database
        cursor.execute(
            "SELECT id_model FROM model_prediksi "
            "WHERE jenis_algoritma = 'Regresi_Linear_Berganda' AND is_aktif = 1 "
            "ORDER BY trained_at DESC LIMIT 1"
        )
        row = cursor.fetchone()
        id_model_rlb_db = row['id_model'] if row else None

        cursor.execute(
            "SELECT id_model FROM model_prediksi "
            "WHERE jenis_algoritma = 'Random_Forest' AND is_aktif = 1 "
            "ORDER BY trained_at DESC LIMIT 1"
        )
        row = cursor.fetchone()
        id_model_rf_db = row['id_model'] if row else None

        cursor.execute("""
            INSERT INTO data_ternak
            (id_peternak, nama_batch, fase, hari, populasi_pagi, mortalitas,
             populasi_akhir, berat_ratarata, mortalitas_kumulatif, tanggal_input)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            peternak_id, nama_batch, fase, hari, populasi, mortalitas,
            populasi_akhir, berat_rata, mortalitas, tanggal_date
        ))
        id_data_ternak_baru = cursor.lastrowid
        print(f"data_ternak inserted: id={id_data_ternak_baru}")

        cursor.execute("""
            INSERT INTO riwayat_prediksi
            (id_peternak, id_data_ternak, id_model_rlb, id_model_rf, prediksi_pakan_kg,
             estimasi_berat_panen, estimasi_populasi_panen, estimasi_bobot_total_kg,
             deviasi_berat_persen, status_nutrisi, tanggal_prediksi, is_saved,
             nama_batch, tanggal_input, hari, fase, populasi_pagi, mortalitas_harian)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            peternak_id, id_data_ternak_baru, id_model_rlb_db, id_model_rf_db,
            total_pakan_rlb, berat_panen_est, populasi_panen, total_bobot,
            deviasi_persen, status_nutrisi, tanggal_input, 1,
            nama_batch, tanggal_input, hari, fase, populasi, mortalitas
        ))
        riwayat_id = cursor.lastrowid
        print(f"riwayat_prediksi inserted: id={riwayat_id} "
              f"(id_model_rlb={id_model_rlb_db}, id_model_rf={id_model_rf_db})")

        if status_nutrisi in ('Peringatan_Ringan', 'Peringatan_Kritis'):
            jenis_peringatan = 'Ringan' if status_nutrisi == 'Peringatan_Ringan' else 'Kritis'
            pesan_notif = (
                f"Deviasi berat {abs(deviasi_persen):.1f}% dari standar pada hari ke-{hari} "
                f"({nama_batch}). "
                + ("Periksa kualitas pakan dan kondisi kandang."
                   if jenis_peringatan == 'Ringan'
                   else "Segera evaluasi pakan dan kesehatan ternak.")
            )
            cursor.execute("""
                INSERT INTO notifikasi_kualitas_pakan
                (id_peternak, id_prediksi, jenis_peringatan, pesan, deviasi_persen, is_dibaca)
                VALUES (%s, %s, %s, %s, %s, 0)
            """, (peternak_id, riwayat_id, jenis_peringatan, pesan_notif, deviasi_persen))
            print(f"notifikasi inserted untuk riwayat_id={riwayat_id}")

        db.commit()

    except Exception as e:
        if db:
            db.rollback()
        print(f"DB error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if db:
            db.close()

    pesan_nutrisi_map = {
        'Normal':            'Berat ayam sesuai standar ayam kampung.',
        'Peringatan_Ringan': 'Berat di bawah standar. Periksa kualitas pakan.',
        'Peringatan_Kritis': 'Berat jauh di bawah standar. Segera evaluasi pakan dan kesehatan.',
    }

    return jsonify({
        'success': True,
        'riwayat_id': riwayat_id,
        'data': {
            'id_prediksi':             riwayat_id,
            'id_peternak':             peternak_id,
            'id_data_ternak':          id_data_ternak_baru,
            'nama_batch':              nama_batch,
            'tanggal_input':           tanggal_input,
            'hari':                    hari,
            'fase':                    fase,
            'populasi_pagi':           populasi,
            'mortalitas_harian':       mortalitas,
            'populasi_akhir':          populasi_panen,
            'total_pakan_rlb':         total_pakan_rlb,
            'prediksi_pakan_kg':       total_pakan_rlb,
            'berat_7hari_rf':          berat_panen_est,
            'estimasi_berat_panen':    berat_panen_est,
            'berat_panen_est':         berat_panen_est,
            'estimasi_populasi_panen': populasi_panen,
            'populasi_panen':          populasi_panen,
            'estimasi_bobot_total_kg': total_bobot,
            'total_bobot_panen':       total_bobot,
            'deviasi_berat_persen':    deviasi_persen,
            'status_nutrisi':          status_nutrisi,
            'pesan_nutrisi':           pesan_nutrisi_map.get(status_nutrisi, ''),
            'standar_berat':           berat_standar,
            'standar_pakan_hari':      standar_pakan_hari_ini,
            'fcr':                     fcr_estimasi,
            'model_raw_pakan':         round(prediksi_pakan_raw, 2),
            'model_raw_berat':         round(estimasi_berat_raw, 2),
        }
    })


@prediksi_bp.route('/riwayat/<int:peternak_id>', methods=['GET'])
def get_riwayat(peternak_id):
    try:
        db     = get_db()
        cursor = db.cursor()
        cursor.execute(
            """SELECT r.*, d.berat_ratarata
               FROM riwayat_prediksi r
               LEFT JOIN data_ternak d ON r.id_data_ternak = d.id_data_ternak
               WHERE r.id_peternak = %s
               ORDER BY r.tanggal_input DESC, r.id_prediksi DESC
               LIMIT 50""",
            (peternak_id,)
        )
        rows = cursor.fetchall()
        for row in rows:
            for k, v in row.items():
                if hasattr(v, 'isoformat'):
                    row[k] = v.isoformat()
            if row.get('prediksi_pakan_kg') is not None:
                row['prediksi_pakan_kg'] = max(0.0, float(row['prediksi_pakan_kg']))
            if row.get('berat_ratarata') is not None:
                row['berat_ratarata'] = float(row['berat_ratarata'])
        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        try:
            db.close()
        except:
            pass


@prediksi_bp.route('/notifikasi/<int:peternak_id>', methods=['GET'])
def get_notifikasi(peternak_id):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """SELECT n.id_notifikasi, n.id_peternak, n.id_prediksi,
                      n.jenis_peringatan, n.pesan, n.deviasi_persen,
                      n.is_dibaca, n.created_at, n.dibaca_at,
                      r.nama_batch, r.hari, r.fase
               FROM notifikasi_kualitas_pakan n
               LEFT JOIN riwayat_prediksi r ON n.id_prediksi = r.id_prediksi
               WHERE n.id_peternak = %s
               ORDER BY n.created_at DESC""",
            (peternak_id,)
        )
        rows = cursor.fetchall()
        notifikasi = []
        for r in rows:
            notifikasi.append({
                'id':               r['id_notifikasi'],
                'id_prediksi':      r['id_prediksi'],
                'jenis_peringatan': r['jenis_peringatan'],
                'pesan':            r['pesan'],
                'deviasi_persen':   float(r['deviasi_persen']),
                'is_dibaca':        bool(r['is_dibaca']),
                'created_at':       r['created_at'].isoformat() if r['created_at'] else None,
                'dibaca_at':        r['dibaca_at'].isoformat() if r['dibaca_at'] else None,
                'nama_batch':       r['nama_batch'] or '-',
                'hari':             r['hari'],
                'fase':             r['fase'],
            })
        return jsonify({'success': True, 'data': notifikasi})
    except Exception as e:
        print(f"GET NOTIFIKASI ERROR: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        try:
            db.close()
        except:
            pass


@prediksi_bp.route('/notifikasi/<int:notifikasi_id>/baca', methods=['PUT'])
def tandai_dibaca(notifikasi_id):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """UPDATE notifikasi_kualitas_pakan
               SET is_dibaca = 1, dibaca_at = NOW()
               WHERE id_notifikasi = %s""",
            (notifikasi_id,)
        )
        db.commit()
        return jsonify({'success': True, 'message': 'Notifikasi ditandai dibaca'})
    except Exception as e:
        print(f"TANDAI DIBACA ERROR: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        try:
            db.close()
        except:
            pass


@prediksi_bp.route('/notifikasi/<int:peternak_id>/baca-semua', methods=['PUT'])
def tandai_semua_dibaca(peternak_id):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """UPDATE notifikasi_kualitas_pakan
               SET is_dibaca = 1, dibaca_at = NOW()
               WHERE id_peternak = %s AND is_dibaca = 0""",
            (peternak_id,)
        )
        db.commit()
        return jsonify({'success': True, 'message': 'Semua notifikasi ditandai dibaca'})
    except Exception as e:
        print(f"TANDAI SEMUA ERROR: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        try:
            db.close()
        except:
            pass