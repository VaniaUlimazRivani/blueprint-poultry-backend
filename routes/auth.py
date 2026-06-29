from flask import Blueprint, request, jsonify
from config import get_db
import bcrypt

auth_bp = Blueprint('auth', __name__)


def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password, hashed):
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    identifier = data.get('identifier', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'Peternak')

    print(f"=== LOGIN REQUEST ===")
    print(f"identifier: '{identifier}' | len: {len(identifier)}")
    print(f"role: '{role}'")

    if not identifier or not password:
        return jsonify({'success': False,
                        'message': 'Username/Email dan password wajib diisi'}), 400

    try:
        db = get_db()
        cursor = db.cursor()

        if role == 'Pengelola':
            cursor.execute(
                "SELECT * FROM pengelola WHERE TRIM(email) = TRIM(%s)", (identifier,))
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
                    'id': user['id_pengelola'],
                    'nama': user['nama'],
                    'email': user['email'],
                }
            })

        else:
            cursor.execute(
                "SELECT * FROM peternak WHERE TRIM(username) = TRIM(%s) OR TRIM(email) = TRIM(%s)",
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
                'role': 'Peternak',
                'user': {
                    'id': user['id_peternak'],
                    'nama': user['nama'],
                    'username': user['username'],
                    'email': user['email'],
                    'no_hp': user['no_hp'],
                    'alamat': user['alamat'],
                    'nama_peternakan': user['nama_peternakan'],
                }
            })

    except Exception as e:
        print(f"ERROR: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    nama = data.get('nama', '').strip()
    username = data.get('username', '').strip()
    no_hp = data.get('no_hp', '').strip()
    email = data.get('email', '').strip() or None
    alamat = data.get('alamat', '').strip() or None
    nama_peternakan = data.get('nama_peternakan', '').strip() or None
    password = data.get('password', '')

    print(f"=== REGISTER REQUEST ===")
    print(f"nama: '{nama}' | username: '{username}' | no_hp: '{no_hp}'")

    if not nama or not username or not no_hp or not password:
        return jsonify({'success': False,
                        'message': 'Data wajib (nama, username, no HP, password) tidak lengkap'}), 400

    try:
        db = get_db()
        cursor = db.cursor()

        cursor.execute(
            "SELECT id_peternak FROM peternak WHERE username = %s OR no_hp = %s",
            (username, no_hp))
        existing = cursor.fetchone()
        if existing:
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
               (nama, email, no_hp, username, password, alamat, nama_peternakan, is_active)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 1)""",
            (nama, email, no_hp, username, hash_password(password), alamat, nama_peternakan)
        )
        db.commit()
        print(f"REGISTER BERHASIL: {username}")
        return jsonify({'success': True,
                        'message': 'Registrasi berhasil'})

    except Exception as e:
        print(f"REGISTER ERROR: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


# ── PENGELOLA ENDPOINTS ────────────────────────────────

@auth_bp.route('/pengelola/peternak', methods=['GET'])
def get_semua_peternak():
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT p.id_peternak, p.nama, p.email, p.no_hp, p.alamat,
                   p.nama_peternakan, p.username, p.is_active, p.created_at,
                   COUNT(DISTINCT r.nama_batch) as total_batch,
                   COUNT(r.id_prediksi) as total_prediksi
            FROM peternak p
            LEFT JOIN riwayat_prediksi r ON p.id_peternak = r.id_peternak
            GROUP BY p.id_peternak
            ORDER BY p.created_at DESC
        """)
        rows = cursor.fetchall()
        result = []
        bulan = ['Jan','Feb','Mar','Apr','Mei','Jun',
                 'Jul','Agu','Sep','Okt','Nov','Des']
        for row in rows:
            dt = row['created_at']
            bergabung = f"{bulan[dt.month-1]} {dt.year}" if dt else '-'
            result.append({
                'id': row['id_peternak'],
                'nama': row['nama'],
                'email': row['email'] or '-',
                'no_hp': row['no_hp'] or '-',
                'alamat': row['alamat'] or '-',
                'nama_peternakan': row['nama_peternakan'] or '-',
                'username': row['username'],
                'is_active': bool(row['is_active']),
                'bergabung': bergabung,
                'total_batch': int(row['total_batch']),
                'total_prediksi': int(row['total_prediksi']),
            })
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        print(f"GET PETERNAK ERROR: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        try: db.close()
        except: pass


@auth_bp.route('/pengelola/peternak/<int:peternak_id>/toggle', methods=['PUT'])
def toggle_status_peternak(peternak_id):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT is_active FROM peternak WHERE id_peternak = %s",
            (peternak_id,)
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False,
                            'message': 'Peternak tidak ditemukan'}), 404
        new_status = 0 if row['is_active'] else 1
        cursor.execute(
            "UPDATE peternak SET is_active = %s WHERE id_peternak = %s",
            (new_status, peternak_id)
        )
        db.commit()
        return jsonify({
            'success': True,
            'is_active': bool(new_status),
            'message': 'Aktif' if new_status else 'Nonaktif'
        })
    except Exception as e:
        print(f"TOGGLE ERROR: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        try: db.close()
        except: pass


@auth_bp.route('/pengelola/statistik', methods=['GET'])
def get_statistik_pengelola():
    try:
        db = get_db()
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
                'batch_aktif': batch_aktif,
                'total_prediksi': total_prediksi,
            }
        })
    except Exception as e:
        print(f"STATISTIK ERROR: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        try: db.close()
        except: pass