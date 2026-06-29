from flask import Blueprint, request, jsonify
from config import get_db

katalog_bp = Blueprint('katalog', __name__)


@katalog_bp.route('/katalog', methods=['GET'])
def get_katalog():
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """SELECT rp.*, GROUP_CONCAT(
                   CONCAT(br.nama_bahan,'|',br.persentase,'|',br.fungsi)
                   ORDER BY br.id_bahan SEPARATOR ';;'
               ) as bahan_list
               FROM racikan_pakan rp
               LEFT JOIN bahan_racikan br ON rp.id_racikan = br.id_racikan
               WHERE rp.is_aktif = 1
               GROUP BY rp.id_racikan
               ORDER BY rp.fase, rp.nama_racikan""")
        rows = cursor.fetchall()
        result = []
        for row in rows:
            bahan = []
            if row['bahan_list']:
                for b in row['bahan_list'].split(';;'):
                    parts = b.split('|')
                    if len(parts) == 3:
                        bahan.append({
                            'nama': parts[0],
                            'persen': float(parts[1]),
                            'fungsi': parts[2]
                        })
            result.append({
                'id': row['id_racikan'],
                'nama': row['nama_racikan'],
                'fase': row['fase'],
                'deskripsi': row['deskripsi'],
                'estimasi_biaya': row['estimasi_biaya_per_kg'],
                'kandungan_protein': float(row['kandungan_protein']),
                'langkah': row['langkah_pembuatan'],
                'bahan': bahan,
                'is_aktif': bool(row['is_aktif']),
            })
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@katalog_bp.route('/katalog/semua', methods=['GET'])
def get_katalog_semua():
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """SELECT rp.*, GROUP_CONCAT(
                   CONCAT(br.nama_bahan,'|',br.persentase,'|',br.fungsi)
                   ORDER BY br.id_bahan SEPARATOR ';;'
               ) as bahan_list
               FROM racikan_pakan rp
               LEFT JOIN bahan_racikan br ON rp.id_racikan = br.id_racikan
               GROUP BY rp.id_racikan
               ORDER BY rp.fase, rp.nama_racikan""")
        rows = cursor.fetchall()
        result = []
        for row in rows:
            bahan = []
            if row['bahan_list']:
                for b in row['bahan_list'].split(';;'):
                    parts = b.split('|')
                    if len(parts) == 3:
                        bahan.append({
                            'nama': parts[0],
                            'persen': float(parts[1]),
                            'fungsi': parts[2]
                        })
            result.append({
                'id': row['id_racikan'],
                'nama': row['nama_racikan'],
                'fase': row['fase'],
                'deskripsi': row['deskripsi'],
                'protein': float(row['kandungan_protein']),
                'biaya': int(row['estimasi_biaya_per_kg']),
                'langkah': row['langkah_pembuatan'],
                'bahan': bahan,
                'aktif': bool(row['is_aktif']),
            })
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@katalog_bp.route('/katalog', methods=['POST'])
def tambah_katalog():
    data = request.get_json()
    nama = data.get('nama', '').strip()
    fase = data.get('fase', 'Starter')
    deskripsi = data.get('deskripsi', '').strip()
    protein = data.get('protein', 0)
    biaya = data.get('biaya', 0)
    langkah = data.get('langkah', '').strip()
    bahan_list = data.get('bahan', [])
    id_pengelola = data.get('id_pengelola', 1)

    if not nama:
        return jsonify({'success': False,
                        'message': 'Nama racikan wajib diisi'}), 400

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """INSERT INTO racikan_pakan
               (id_pengelola, nama_racikan, fase, deskripsi,
                estimasi_biaya_per_kg, kandungan_protein,
                langkah_pembuatan, is_aktif)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 1)""",
            (id_pengelola, nama, fase,
             deskripsi or f'Racikan pakan {fase.lower()} berbahan lokal.',
             biaya, protein, langkah or '-')
        )
        new_id = cursor.lastrowid

        for b in bahan_list:
            b_nama = (b.get('nama') or '').strip()
            b_persen = b.get('persen', 0)
            b_fungsi = (b.get('fungsi') or '').strip()
            if b_nama:
                cursor.execute(
                    """INSERT INTO bahan_racikan
                       (id_racikan, nama_bahan, persentase, fungsi)
                       VALUES (%s, %s, %s, %s)""",
                    (new_id, b_nama, b_persen, b_fungsi)
                )

        db.commit()
        return jsonify({
            'success': True,
            'message': 'Racikan berhasil ditambahkan',
            'id': new_id
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@katalog_bp.route('/katalog/<int:katalog_id>', methods=['PUT'])
def edit_katalog(katalog_id):
    data = request.get_json()
    nama = data.get('nama', '').strip()
    fase = data.get('fase', 'Starter')
    deskripsi = data.get('deskripsi', '').strip()
    protein = data.get('protein', 0)
    biaya = data.get('biaya', 0)
    langkah = data.get('langkah', '').strip()
    bahan_list = data.get('bahan', [])

    if not nama:
        return jsonify({'success': False,
                        'message': 'Nama racikan wajib diisi'}), 400

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """UPDATE racikan_pakan
               SET nama_racikan=%s, fase=%s, deskripsi=%s,
                   kandungan_protein=%s, estimasi_biaya_per_kg=%s,
                   langkah_pembuatan=%s
               WHERE id_racikan=%s""",
            (nama, fase, deskripsi, protein, biaya, langkah, katalog_id)
        )

        # Hapus bahan lama, masukkan bahan baru
        cursor.execute(
            "DELETE FROM bahan_racikan WHERE id_racikan = %s",
            (katalog_id,))

        for b in bahan_list:
            b_nama = (b.get('nama') or '').strip()
            b_persen = b.get('persen', 0)
            b_fungsi = (b.get('fungsi') or '').strip()
            if b_nama:
                cursor.execute(
                    """INSERT INTO bahan_racikan
                       (id_racikan, nama_bahan, persentase, fungsi)
                       VALUES (%s, %s, %s, %s)""",
                    (katalog_id, b_nama, b_persen, b_fungsi)
                )

        db.commit()
        return jsonify({
            'success': True,
            'message': 'Racikan berhasil diperbarui'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@katalog_bp.route('/katalog/<int:katalog_id>', methods=['DELETE'])
def hapus_katalog(katalog_id):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "DELETE FROM bahan_racikan WHERE id_racikan = %s",
            (katalog_id,))
        cursor.execute(
            "DELETE FROM racikan_pakan WHERE id_racikan = %s",
            (katalog_id,))
        db.commit()
        return jsonify({
            'success': True,
            'message': 'Racikan berhasil dihapus'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@katalog_bp.route('/katalog/<int:katalog_id>/toggle', methods=['PUT'])
def toggle_katalog(katalog_id):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT is_aktif FROM racikan_pakan WHERE id_racikan = %s",
            (katalog_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False,
                            'message': 'Racikan tidak ditemukan'}), 404
        new_status = 0 if row['is_aktif'] else 1
        cursor.execute(
            "UPDATE racikan_pakan SET is_aktif=%s WHERE id_racikan=%s",
            (new_status, katalog_id))
        db.commit()
        return jsonify({
            'success': True,
            'is_aktif': bool(new_status),
            'message': 'Aktif' if new_status else 'Nonaktif'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()