import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_percentage_error, r2_score
import joblib
import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

def get_data_from_db():
    db = pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', 'blueprint_poultry'),
        cursorclass=pymysql.cursors.DictCursor
    )
    cursor = db.cursor()
    cursor.execute("SELECT * FROM dataset_historis")
    rows = cursor.fetchall()
    db.close()
    return pd.DataFrame(rows)

def train_models():
    print("Mengambil data dari database...")
    df = get_data_from_db()

    if len(df) < 10:
        print("Data terlalu sedikit, gunakan dataset CSV")
        df = pd.read_excel(
            'dataset_ayam_kampung_BARU_60hari.xlsx',
            sheet_name='Dataset Baru (60 Hari)'
        )

    print(f"Total data: {len(df)} baris")

    # Encode fase
    df['fase_encoded'] = df['Fase'].map(
        {'Starter': 0, 'Finisher': 1}) if 'Fase' in df.columns else \
        df['fase'].map({'Starter': 0, 'Finisher': 1})

    # Pilih kolom yang sesuai nama database atau excel
    col_map = {
        'hari': ['Hari', 'hari'],
        'populasi': ['Populasi Akhir Hari', 'populasi_akhir'],
        'mortalitas_kum': ['Mortalitas_Kumulatif',
                           'mortalitas_kumulatif'],
        'berat': ['Berat Rata-rata (g)', 'berat_rata2'],
        'pakan': ['Total Pakan Harian (kg)', 'total_pakan_harian'],
    }

    def get_col(df, keys):
        for k in keys:
            if k in df.columns:
                return df[k]
        raise KeyError(f"Kolom tidak ditemukan: {keys}")

    X = pd.DataFrame({
        'hari': get_col(df, col_map['hari']),
        'populasi': get_col(df, col_map['populasi']),
        'mortalitas_kum': get_col(df, col_map['mortalitas_kum']),
        'berat': get_col(df, col_map['berat']),
        'fase': df['fase_encoded'],
    })

    y_pakan = get_col(df, col_map['pakan'])
    y_berat = get_col(df, col_map['berat'])

    # Split data
    X_train, X_test, y_train_pakan, y_test_pakan = train_test_split(
        X, y_pakan, test_size=0.2, random_state=42)
    _, _, y_train_berat, y_test_berat = train_test_split(
        X, y_berat, test_size=0.2, random_state=42)

    # Scaling
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Training RLB
    print("\nTraining Regresi Linear Berganda...")
    rlb = LinearRegression()
    rlb.fit(X_train_scaled, y_train_pakan)
    y_pred_rlb = rlb.predict(X_test_scaled)
    mse_rlb = mean_squared_error(y_test_pakan, y_pred_rlb)
    mape_rlb = mean_absolute_percentage_error(
        y_test_pakan, y_pred_rlb) * 100
    r2_rlb = r2_score(y_test_pakan, y_pred_rlb)
    print(f"RLB — MSE: {mse_rlb:.4f} | RMSE: {mse_rlb**0.5:.4f} "
          f"| MAPE: {mape_rlb:.2f}% | R²: {r2_rlb:.4f}")

    # Training Random Forest
    print("\nTraining Random Forest Regression...")
    rf = RandomForestRegressor(
        n_estimators=100, random_state=42, max_depth=10)
    rf.fit(X_train_scaled, y_train_berat)
    y_pred_rf = rf.predict(X_test_scaled)
    mse_rf = mean_squared_error(y_test_berat, y_pred_rf)
    mape_rf = mean_absolute_percentage_error(
        y_test_berat, y_pred_rf) * 100
    r2_rf = r2_score(y_test_berat, y_pred_rf)
    print(f"RF  — MSE: {mse_rf:.4f} | RMSE: {mse_rf**0.5:.4f} "
          f"| MAPE: {mape_rf:.2f}% | R²: {r2_rf:.4f}")

    # Simpan model
    save_path = os.path.join(
        os.path.dirname(__file__), 'saved')
    os.makedirs(save_path, exist_ok=True)
    joblib.dump(rlb, os.path.join(save_path, 'model_rlb.pkl'))
    joblib.dump(rf, os.path.join(save_path, 'model_rf.pkl'))
    joblib.dump(scaler, os.path.join(save_path, 'scaler.pkl'))
    print(f"\nModel disimpan di: {save_path}")

    return {
        'rlb': {'mse': round(mse_rlb, 4),
                'rmse': round(mse_rlb**0.5, 4),
                'mape': round(mape_rlb, 2),
                'r2': round(r2_rlb, 4)},
        'rf': {'mse': round(mse_rf, 4),
               'rmse': round(mse_rf**0.5, 4),
               'mape': round(mape_rf, 2),
               'r2': round(r2_rf, 4)},
    }

if __name__ == '__main__':
    hasil = train_models()
    print("\nHasil Training:")
    print(f"RLB: {hasil['rlb']}")
    print(f"RF:  {hasil['rf']}")