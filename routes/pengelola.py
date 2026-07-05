from flask import Blueprint, request, jsonify
from config import get_db
import pandas as pd
import io

pengelola_bp = Blueprint('pengelola', __name__)


@pengelola_bp.route('/pengelola/statistik', methods=['GET'])
def get_statistik():
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM peternak WHERE is_active = 1")
        total_peternak = cursor.fetchone()['total']
        cursor.execute("SELECT COUNT(*) as total FROM riwayat_prediksi")
        total_prediksi = cursor.fetchone()['total']
        cursor.execute("SELECT COUNT(*) as total FROM dataset_historis WHERE is_aktif = 1")
        total_dataset = cursor.fetchone()['total']
        return jsonify({
            'success': True,
            'data': {
                'total_peternak_aktif': total_peternak,
                'total_prediksi': total_prediksi,
                'total_dataset': total_dataset,
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@pengelola_bp.route('/pengelola/peternak', methods=['GET'])
def get_daftar_peternak():
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT p.id_peternak, p.nama, p.email, p.no_hp,
                   p.username, p.alamat, p.nama_peternakan,
                   p.is_active, p.created_at,
                   COUNT(r.id_prediksi) as total_prediksi
            FROM peternak p
            LEFT JOIN riwayat_prediksi r ON p.id_peternak = r.id_peternak
            GROUP BY p.id_peternak
            ORDER BY p.created_at DESC
        """)
        rows = cursor.fetchall()
        for row in rows:
            if row.get('created_at'):
                row['created_at'] = row['created_at'].isoformat()
            row['is_active'] = bool(row['is_active'])
        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@pengelola_bp.route('/pengelola/peternak/<int:peternak_id>/toggle', methods=['PUT'])
def toggle_status_peternak(peternak_id):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT is_active FROM peternak WHERE id_peternak = %s", (peternak_id,))
        user = cursor.fetchone()
        if not user:
            return jsonify({'success': False, 'message': 'Peternak tidak ditemukan'}), 404
        new_status = 0 if user['is_active'] else 1
        cursor.execute(
            "UPDATE peternak SET is_active = %s WHERE id_peternak = %s",
            (new_status, peternak_id))
        db.commit()
        return jsonify({'success': True, 'is_active': bool(new_status)})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@pengelola_bp.route('/pengelola/peternak/<int:peternak_id>', methods=['DELETE'])
def hapus_peternak(peternak_id):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "DELETE FROM peternak WHERE id_peternak = %s", (peternak_id,))
        db.commit()
        return jsonify({'success': True, 'message': 'Akun dihapus'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@pengelola_bp.route('/pengelola/dataset/ringkasan', methods=['GET'])
def get_ringkasan_dataset():
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT COUNT(*) as total FROM dataset_historis WHERE is_aktif = 1")
        total_baris = cursor.fetchone()['total']
        cursor.execute("""
            SELECT nama_batch,
                   COUNT(*) as jumlah_hari,
                   MIN(berat_ratarata_gram) as berat_awal,
                   MAX(berat_ratarata_gram) as berat_akhir,
                   SUM(total_pakan_harian_kg) as total_pakan,
                   MAX(populasi_pagi) as populasi_awal
            FROM dataset_historis
            WHERE is_aktif = 1
            GROUP BY nama_batch
            ORDER BY nama_batch
        """)
        rows = cursor.fetchall()
        for row in rows:
            for k, v in row.items():
                if hasattr(v, 'isoformat'):
                    row[k] = v.isoformat()
                try:
                    if v is not None:
                        row[k] = round(float(v), 2)
                except (TypeError, ValueError):
                    pass
        return jsonify({
            'success': True,
            'total_baris': total_baris,
            'total_batch': len(rows),
            'data': rows
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@pengelola_bp.route('/pengelola/dataset/batch/<nama_batch>', methods=['DELETE'])
def hapus_batch(nama_batch):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "UPDATE dataset_historis SET is_aktif = 0 WHERE nama_batch = %s",
            (nama_batch,))
        db.commit()
        affected = cursor.rowcount
        return jsonify({
            'success': True,
            'message': f'{affected} baris batch {nama_batch} dinonaktifkan'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@pengelola_bp.route('/pengelola/dataset/upload', methods=['POST'])
def upload_dataset():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'File tidak ditemukan'}), 400
    file = request.files['file']
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'success': False, 'message': 'Format harus .xlsx atau .xls'}), 400
    pengelola_id = int(request.headers.get('X-Pengelola-Id', 1))
    try:
        contents = file.read()
        df = pd.read_excel(io.BytesIO(contents))
        required_cols = ['Batch', 'Hari', 'Fase', 'Populasi_Pagi',
                         'Mortalitas', 'Berat_Ratarata_Gram', 'Total_Pakan_Harian_Kg']
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            return jsonify({
                'success': False,
                'message': f'Kolom tidak lengkap: {", ".join(missing)}'
            }), 400
        db = get_db()
        cursor = db.cursor()
        inserted = 0
        errors = 0
        for _, row in df.iterrows():
            try:
                populasi_pagi = int(row.get('Populasi_Pagi', 0))
                mortalitas = int(row.get('Mortalitas', 0))
                populasi_akhir = int(row.get('Populasi_Akhir',
                                             populasi_pagi - mortalitas))
                total_pakan = float(row.get('Total_Pakan_Harian_Kg', 0))
                pakan_per_ekor = round(
                    (total_pakan * 1000) / populasi_pagi, 2) if populasi_pagi > 0 else 0
                cursor.execute("""
                    INSERT INTO dataset_historis
                    (id_pengelola, nama_batch, fase, hari, populasi_pagi,
                     mortalitas, populasi_akhir, pakan_per_ekor_gram,
                     total_pakan_harian_kg, berat_ratarata_gram,
                     mortalitas_kumulatif, is_aktif)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
                """, (
                    pengelola_id,
                    str(row.get('Batch', '')),
                    str(row.get('Fase', 'Starter')),
                    int(row.get('Hari', 0)),
                    populasi_pagi,
                    mortalitas,
                    populasi_akhir,
                    pakan_per_ekor,
                    total_pakan,
                    int(row.get('Berat_Ratarata_Gram', 0)),
                    int(row.get('Mortalitas_Kumulatif', mortalitas)),
                ))
                inserted += 1
            except Exception as row_err:
                print(f"Row error: {row_err}")
                errors += 1
        db.commit()
        return jsonify({
            'success': True,
            'message': f'{inserted} baris berhasil diimpor.',
            'inserted': inserted,
            'errors': errors,
            'total_rows': len(df)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        try:
            db.close()
        except:
            pass


@pengelola_bp.route('/pengelola/dataset', methods=['GET'])
def get_dataset():
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT * FROM dataset_historis
            WHERE is_aktif = 1
            ORDER BY id_dataset DESC LIMIT 100
        """)
        rows = cursor.fetchall()
        for row in rows:
            for k, v in row.items():
                if hasattr(v, 'isoformat'):
                    row[k] = v.isoformat()
        return jsonify({'success': True, 'data': rows, 'total': len(rows)})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()

@pengelola_bp.route('/pengelola/data-ternak', methods=['GET'])
def get_data_ternak():
    try:
        db = get_db()
        cursor = db.cursor()

        page       = int(request.args.get('page', 1))
        per_page   = 20
        offset     = (page - 1) * per_page
        fase       = request.args.get('fase', '')
        batch      = request.args.get('batch', '')
        peternak   = request.args.get('peternak', '')

        conditions = []
        params     = []

        if fase:
            conditions.append("dt.fase = %s")
            params.append(fase)
        if batch:
            conditions.append("dt.nama_batch = %s")
            params.append(batch)
        if peternak:
            conditions.append("dt.id_peternak = %s")
            params.append(peternak)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        # Total count
        cursor.execute(f"""
            SELECT COUNT(*) as total
            FROM data_ternak dt
            JOIN peternak p ON dt.id_peternak = p.id_peternak
            {where}
        """, params)
        total = cursor.fetchone()['total']

        # Data
        cursor.execute(f"""
            SELECT dt.id_data_ternak, dt.id_peternak, p.nama as nama_peternak,
                   dt.nama_batch, dt.fase, dt.hari, dt.populasi_pagi,
                   dt.mortalitas, dt.populasi_akhir, dt.berat_ratarata,
                   dt.mortalitas_kumulatif, dt.tanggal_input, dt.created_at
            FROM data_ternak dt
            JOIN peternak p ON dt.id_peternak = p.id_peternak
            {where}
            ORDER BY dt.tanggal_input DESC, dt.created_at DESC
            LIMIT %s OFFSET %s
        """, params + [per_page, offset])

        rows = cursor.fetchall()
        for row in rows:
            for k, v in row.items():
                if hasattr(v, 'isoformat'):
                    row[k] = v.isoformat()
                try:
                    if isinstance(v, __import__('decimal').Decimal):
                        row[k] = float(v)
                except:
                    pass

        # Daftar batch & peternak untuk filter dropdown
        cursor.execute("""
            SELECT DISTINCT nama_batch FROM data_ternak ORDER BY nama_batch
        """)
        batch_list = [r['nama_batch'] for r in cursor.fetchall()]

        cursor.execute("""
            SELECT id_peternak, nama FROM peternak
            WHERE id_peternak IN (SELECT DISTINCT id_peternak FROM data_ternak)
            ORDER BY nama
        """)
        peternak_list = cursor.fetchall()

        return jsonify({
            'success'       : True,
            'data'          : rows,
            'total'         : total,
            'page'          : page,
            'per_page'      : per_page,
            'total_pages'   : -(-total // per_page),
            'batch_list'    : batch_list,
            'peternak_list' : peternak_list,
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@pengelola_bp.route('/pengelola/data-ternak/<int:id_data>', methods=['GET'])
def get_detail_data_ternak(id_data):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT dt.*, p.nama as nama_peternak
            FROM data_ternak dt
            JOIN peternak p ON dt.id_peternak = p.id_peternak
            WHERE dt.id_data_ternak = %s
        """, (id_data,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False, 'message': 'Data tidak ditemukan'}), 404
        for k, v in row.items():
            if hasattr(v, 'isoformat'):
                row[k] = v.isoformat()
            try:
                if isinstance(v, __import__('decimal').Decimal):
                    row[k] = float(v)
            except:
                pass
        return jsonify({'success': True, 'data': row})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@pengelola_bp.route('/pengelola/data-ternak/<int:id_data>', methods=['PUT'])
def update_data_ternak(id_data):
    try:
        body = request.get_json()
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            UPDATE data_ternak SET
                nama_batch = %s, fase = %s, hari = %s,
                populasi_pagi = %s, mortalitas = %s, populasi_akhir = %s,
                berat_ratarata = %s, mortalitas_kumulatif = %s, tanggal_input = %s
            WHERE id_data_ternak = %s
        """, (
            body['nama_batch'], body['fase'], body['hari'],
            body['populasi_pagi'], body['mortalitas'], body['populasi_akhir'],
            body['berat_ratarata'], body['mortalitas_kumulatif'], body['tanggal_input'],
            id_data
        ))
        db.commit()
        return jsonify({'success': True, 'message': 'Data berhasil diperbarui'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@pengelola_bp.route('/pengelola/data-ternak/<int:id_data>', methods=['DELETE'])
def delete_data_ternak(id_data):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("DELETE FROM data_ternak WHERE id_data_ternak = %s", (id_data,))
        db.commit()
        return jsonify({'success': True, 'message': 'Data berhasil dihapus'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()