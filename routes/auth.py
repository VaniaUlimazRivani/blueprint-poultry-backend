import os
import time
from flask import Blueprint, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from config import get_db
import bcrypt

auth_bp = Blueprint('auth', __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}


def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password, hashed):
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ── LOGIN ─────────────────────────────────────────────────
@auth_bp.route('/login', methods=['POST'])
def login():
    data       = request.get_json()
    identifier = data.get('identifier', '').strip()
    password   = data.get('password', '')
    role       = data.get('role', 'Peternak')

    print(f"=== LOGIN REQUEST ===")
    print(f"identifier: '{identifier}' | len: {len(identifier)}")
    print(f"role: '{role}'")

    if not identifier or not password:
        return jsonify({'success': False,
                        'message': 'Username/Email dan password wajib diisi'}), 400

    try:
        db     = get_db()
        cursor = db.cursor()

        if role == 'Pengelola':
            cursor.execute(
                "SELECT * FROM pengelola WHERE TRIM(email) = TRIM(%s)",
                (identifier,))
            user = cursor.fetchone()
            if not user:
                return jsonify({'success': False,
                                'message': 'Akun tidak ditemukan'}), 404
            if not check_password(password, user['password']):
                return jsonify({'success': False,
                                'message': 'Password salah'}), 401
            return jsonify({
                'success': True,
                'message': 'Login berhasil',
                'role': 'Pengelola',
                'user': {
                    'id':    user['id_pengelola'],
                    'nama':  user['nama'],
                    'email': user['email'],
                }
            })

        else:
            cursor.execute(
                """SELECT * FROM peternak
                   WHERE TRIM(username) = TRIM(%s)
                      OR TRIM(email)    = TRIM(%s)""",
                (identifier, identifier))
            user = cursor.fetchone()
            print(f"PETERNAK QUERY RESULT: {user}")

            if not user:
                return jsonify({'success': False,
                                'message': 'Akun tidak ditemukan'}), 404
            if not check_password(password, user['password']):
                return jsonify({'success': False,
                                'message': 'Password salah'}), 401
            if not user['is_active']:
                return jsonify({'success': False,
                                'message': 'Akun dinonaktifkan'}), 403
            return jsonify({
                'success': True,
                'message': 'Login berhasil',
                'role':    'Peternak',
                'user': {
                    'id':              user['id_peternak'],
                    'nama':            user['nama'],
                    'username':        user['username'],
                    'email':           user['email'],
                    'no_hp':           user['no_hp'],
                    'alamat':          user['alamat'],
                    'nama_peternakan': user['nama_peternakan'],
                    'foto_profil':     user['foto_profil'],
                }
            })

    except Exception as e:
        print(f"ERROR: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


# ── REGISTER ──────────────────────────────────────────────
@auth_bp.route('/register', methods=['POST'])
def register():
    data            = request.get_json()
    nama            = data.get('nama', '').strip()
    username        = data.get('username', '').strip()
    no_hp           = data.get('no_hp', '').strip()
    email           = data.get('email', '').strip() or None
    alamat          = data.get('alamat', '').strip() or None
    nama_peternakan = data.get('nama_peternakan', '').strip() or None
    password        = data.get('password', '')

    if not nama or not username or not no_hp or not password:
        return jsonify({'success': False,
                        'message': 'Data wajib tidak lengkap'}), 400

    try:
        db     = get_db()
        cursor = db.cursor()

        cursor.execute(
            "SELECT id_peternak FROM peternak WHERE username = %s OR no_hp = %s",
            (username, no_hp))
        if cursor.fetchone():
            return jsonify({'success': False,
                            'message': 'Username atau No HP sudah terdaftar'}), 409

        if email:
            cursor.execute(
                "SELECT id_peternak FROM peternak WHERE email = %s", (email,))
            if cursor.fetchone():
                return jsonify({'success': False,
                                'message': 'Email sudah terdaftar'}), 409

        cursor.execute(
            """INSERT INTO peternak
               (nama, email, no_hp, username, password,
                alamat, nama_peternakan, is_active)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 1)""",
            (nama, email, no_hp, username,
             hash_password(password), alamat, nama_peternakan)
        )
        db.commit()
        return jsonify({'success': True, 'message': 'Registrasi berhasil'})

    except Exception as e:
        print(f"REGISTER ERROR: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


# ── UPDATE PROFIL ─────────────────────────────────────────
@auth_bp.route('/peternak/<int:peternak_id>/update', methods=['PUT'])
def update_profil(peternak_id):
    data            = request.get_json()
    nama            = data.get('nama', '').strip()
    email           = data.get('email', '').strip() or None
    no_hp           = data.get('no_hp', '').strip()
    alamat          = data.get('alamat', '').strip() or None
    nama_peternakan = data.get('nama_peternakan', '').strip() or None

    if not nama or not no_hp:
        return jsonify({'success': False,
                        'message': 'Nama dan No HP wajib diisi'}), 400

    try:
        db     = get_db()
        cursor = db.cursor()

        cursor.execute(
            "SELECT id_peternak FROM peternak WHERE id_peternak = %s",
            (peternak_id,))
        if not cursor.fetchone():
            return jsonify({'success': False,
                            'message': 'Peternak tidak ditemukan'}), 404

        cursor.execute("""
            UPDATE peternak
            SET nama = %s, email = %s, no_hp = %s,
                alamat = %s, nama_peternakan = %s, updated_at = NOW()
            WHERE id_peternak = %s
        """, (nama, email, no_hp, alamat, nama_peternakan, peternak_id))
        db.commit()

        cursor.execute(
            "SELECT * FROM peternak WHERE id_peternak = %s", (peternak_id,))
        user = cursor.fetchone()

        return jsonify({
            'success': True,
            'message': 'Profil berhasil diperbarui',
            'user': {
                'id':              user['id_peternak'],
                'nama':            user['nama'],
                'username':        user['username'],
                'email':           user['email'],
                'no_hp':           user['no_hp'],
                'alamat':          user['alamat'],
                'nama_peternakan': user['nama_peternakan'],
                'foto_profil':     user['foto_profil'],
            }
        })

    except Exception as e:
        print(f"UPDATE PROFIL ERROR: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        try:
            db.close()
        except:
            pass


# ── STATISTIK PETERNAK ────────────────────────────────────
@auth_bp.route('/peternak/<int:peternak_id>/statistik', methods=['GET'])
def get_statistik_peternak(peternak_id):
    try:
        db     = get_db()
        cursor = db.cursor()

        cursor.execute("""
            SELECT COUNT(DISTINCT nama_batch) as total_batch
            FROM riwayat_prediksi WHERE id_peternak = %s
        """, (peternak_id,))
        total_batch = cursor.fetchone()['total_batch']

        cursor.execute("""
            SELECT COUNT(*) as total_prediksi
            FROM riwayat_prediksi WHERE id_peternak = %s
        """, (peternak_id,))
        total_prediksi = cursor.fetchone()['total_prediksi']

        cursor.execute(
            "SELECT created_at FROM peternak WHERE id_peternak = %s",
            (peternak_id,))
        row = cursor.fetchone()
        bulan     = ['Jan','Feb','Mar','Apr','Mei','Jun',
                     'Jul','Agu','Sep','Okt','Nov','Des']
        dt        = row['created_at'] if row else None
        bergabung = f"{bulan[dt.month-1]} {dt.year}" if dt else '-'

        return jsonify({
            'success': True,
            'data': {
                'total_batch':    int(total_batch),
                'total_prediksi': int(total_prediksi),
                'bergabung':      bergabung,
            }
        })

    except Exception as e:
        print(f"STATISTIK PETERNAK ERROR: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        try:
            db.close()
        except:
            pass


# ── PENGELOLA: SEMUA PETERNAK ─────────────────────────────
@auth_bp.route('/pengelola/peternak', methods=['GET'])
def get_semua_peternak():
    try:
        db     = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT p.id_peternak, p.nama, p.email, p.no_hp, p.alamat,
                   p.nama_peternakan, p.username, p.is_active, p.created_at,
                   COUNT(DISTINCT r.nama_batch) as total_batch,
                   COUNT(r.id_prediksi)         as total_prediksi
            FROM peternak p
            LEFT JOIN riwayat_prediksi r ON p.id_peternak = r.id_peternak
            GROUP BY p.id_peternak
            ORDER BY p.created_at DESC
        """)
        rows  = cursor.fetchall()
        bulan = ['Jan','Feb','Mar','Apr','Mei','Jun',
                 'Jul','Agu','Sep','Okt','Nov','Des']
        result = []
        for row in rows:
            dt        = row['created_at']
            bergabung = f"{bulan[dt.month-1]} {dt.year}" if dt else '-'
            result.append({
                'id':              row['id_peternak'],
                'nama':            row['nama'],
                'email':           row['email'] or '-',
                'no_hp':           row['no_hp'] or '-',
                'alamat':          row['alamat'] or '-',
                'nama_peternakan': row['nama_peternakan'] or '-',
                'username':        row['username'],
                'is_active':       bool(row['is_active']),
                'bergabung':       bergabung,
                'total_batch':     int(row['total_batch']),
                'total_prediksi':  int(row['total_prediksi']),
            })
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        print(f"GET PETERNAK ERROR: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        try:
            db.close()
        except:
            pass


# ── PENGELOLA: TOGGLE STATUS PETERNAK ────────────────────
@auth_bp.route('/pengelola/peternak/<int:peternak_id>/toggle', methods=['PUT'])
def toggle_status_peternak(peternak_id):
    try:
        db     = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT is_active FROM peternak WHERE id_peternak = %s",
            (peternak_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False,
                            'message': 'Peternak tidak ditemukan'}), 404
        new_status = 0 if row['is_active'] else 1
        cursor.execute(
            "UPDATE peternak SET is_active = %s WHERE id_peternak = %s",
            (new_status, peternak_id))
        db.commit()
        return jsonify({
            'success': True,
            'is_active': bool(new_status),
            'message':   'Aktif' if new_status else 'Nonaktif'
        })
    except Exception as e:
        print(f"TOGGLE ERROR: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        try:
            db.close()
        except:
            pass


# ── PENGELOLA: STATISTIK ──────────────────────────────────
@auth_bp.route('/pengelola/statistik', methods=['GET'])
def get_statistik_pengelola():
    try:
        db     = get_db()
        cursor = db.cursor()

        cursor.execute("SELECT COUNT(*) as total FROM peternak")
        total_peternak = cursor.fetchone()['total']

        cursor.execute("""
            SELECT COUNT(DISTINCT nama_batch) as total
            FROM riwayat_prediksi
            WHERE DATE(tanggal_input) >= DATE_SUB(CURDATE(), INTERVAL 60 DAY)
        """)
        batch_aktif = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) as total FROM riwayat_prediksi")
        total_prediksi = cursor.fetchone()['total']

        return jsonify({
            'success': True,
            'data': {
                'total_peternak': total_peternak,
                'batch_aktif':    batch_aktif,
                'total_prediksi': total_prediksi,
            }
        })
    except Exception as e:
        print(f"STATISTIK ERROR: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        try:
            db.close()
        except:
            pass


# ── GANTI PASSWORD ────────────────────────────────────────
@auth_bp.route('/peternak/<int:peternak_id>/ganti-password', methods=['PUT'])
def ganti_password(peternak_id):
    data          = request.get_json()
    password_lama = data.get('password_lama', '')
    password_baru = data.get('password_baru', '')

    if not password_lama or not password_baru:
        return jsonify({'success': False,
                        'message': 'Password lama dan baru wajib diisi'}), 400
    if len(password_baru) < 8:
        return jsonify({'success': False,
                        'message': 'Password baru minimal 8 karakter'}), 400

    try:
        db     = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT password FROM peternak WHERE id_peternak = %s",
            (peternak_id,))
        user = cursor.fetchone()
        if not user:
            return jsonify({'success': False,
                            'message': 'Akun tidak ditemukan'}), 404
        if not check_password(password_lama, user['password']):
            return jsonify({'success': False,
                            'message': 'Password lama tidak sesuai'}), 401

        cursor.execute(
            "UPDATE peternak SET password = %s, updated_at = NOW() "
            "WHERE id_peternak = %s",
            (hash_password(password_baru), peternak_id)
        )
        db.commit()
        return jsonify({'success': True, 'message': 'Password berhasil diubah'})

    except Exception as e:
        print(f"GANTI PASSWORD ERROR: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        try:
            db.close()
        except:
            pass


# ── UPLOAD FOTO PROFIL ────────────────────────────────────
@auth_bp.route('/peternak/<int:peternak_id>/foto', methods=['POST'])
def upload_foto(peternak_id):
    if 'foto' not in request.files:
        return jsonify({'success': False,
                        'message': 'Tidak ada file foto'}), 400

    file = request.files['foto']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'File kosong'}), 400
    if not allowed_file(file.filename):
        return jsonify({'success': False,
                        'message': 'Format hanya JPG, PNG, WEBP'}), 400

    try:
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        db     = get_db()
        cursor = db.cursor()

        # Hapus foto lama kalau ada
        cursor.execute(
            "SELECT foto_profil FROM peternak WHERE id_peternak = %s",
            (peternak_id,))
        row = cursor.fetchone()
        if row and row['foto_profil']:
            old_path = os.path.join(UPLOAD_FOLDER, row['foto_profil'])
            if os.path.exists(old_path):
                os.remove(old_path)

        # Simpan foto baru dengan nama unik
        ext      = file.filename.rsplit('.', 1)[1].lower()
        filename = f"peternak_{peternak_id}_{int(time.time())}.{ext}"
        file.save(os.path.join(UPLOAD_FOLDER, filename))

        # Update database
        cursor.execute(
            "UPDATE peternak SET foto_profil = %s WHERE id_peternak = %s",
            (filename, peternak_id))
        db.commit()

        return jsonify({
            'success':  True,
            'message':  'Foto berhasil diupload',
            'foto_url': f'/api/foto/{filename}'
        })

    except Exception as e:
        print(f"UPLOAD FOTO ERROR: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        try:
            db.close()
        except:
            pass


# ── SERVE FOTO ────────────────────────────────────────────
@auth_bp.route('/foto/<filename>', methods=['GET'])
def get_foto(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)