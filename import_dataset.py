# import_dataset.py
import pandas as pd
import pymysql

df = pd.read_excel('dataset_blueprint_poultry_FINAL.xlsx', sheet_name='Dataset')
print(f"Total baris: {len(df)}")
print(f"Kolom: {list(df.columns)}")

conn = pymysql.connect(
    host='localhost', user='root', password='',
    database='blueprint_poultry', charset='utf8mb4'
)
cursor = conn.cursor()
inserted = 0

for _, row in df.iterrows():
    populasi_pagi  = int(row['Populasi_Pagi'])
    mortalitas     = int(row['Mortalitas'])
    populasi_akhir = int(row.get('Populasi_Akhir', populasi_pagi - mortalitas))
    total_pakan    = float(row['Total_Pakan_Harian_Kg'])
    pakan_per_ekor = round((total_pakan * 1000) / populasi_pagi, 2) if populasi_pagi > 0 else 0

    cursor.execute("""
        INSERT INTO dataset_historis
        (id_pengelola, nama_batch, fase, hari, populasi_pagi,
         mortalitas, populasi_akhir, pakan_per_ekor_gram,
         total_pakan_harian_kg, berat_ratarata_gram,
         mortalitas_kumulatif, is_aktif)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
    """, (
        1,
        str(row['Batch']),
        str(row['Fase']),
        int(row['Hari']),
        populasi_pagi,
        mortalitas,
        populasi_akhir,
        pakan_per_ekor,
        total_pakan,
        int(row['Berat_Ratarata_Gram']),
        int(row.get('Mortalitas_Kumulatif', mortalitas)),
    ))
    inserted += 1

conn.commit()
conn.close()
print(f"Berhasil import {inserted} baris!")