import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_percentage_error, r2_score
import joblib, os

df = pd.read_excel('dataset_blueprint_poultry_FINAL.xlsx', sheet_name='Dataset')
print(f"Dataset: {df.shape[0]} baris")

df['fase_encoded'] = df['Fase'].map({'Starter': 0, 'Finisher': 1})

# ── RLB: Prediksi Total Pakan Harian ──────────────────────
X_rlb = df[['Hari', 'Populasi_Pagi', 'Mortalitas',
             'Mortalitas_Kumulatif', 'Berat_Ratarata_Gram',
             'fase_encoded']].values
y_rlb = df['Total_Pakan_Harian_Kg'].values

X_train_r, X_test_r, y_train_r, y_test_r = train_test_split(
    X_rlb, y_rlb, test_size=0.2, random_state=42)

scaler_rlb = StandardScaler()
X_train_rs = scaler_rlb.fit_transform(X_train_r)
X_test_rs  = scaler_rlb.transform(X_test_r)

print("\n[1] Training Regresi Linear Berganda (prediksi pakan harian)...")
rlb = LinearRegression()
rlb.fit(X_train_rs, y_train_r)
yp_pred  = rlb.predict(X_test_rs)
mape_rlb = mean_absolute_percentage_error(y_test_r, yp_pred) * 100
r2_rlb   = r2_score(y_test_r, yp_pred)
rmse_rlb = np.sqrt(mean_squared_error(y_test_r, yp_pred))
print(f"    RMSE : {rmse_rlb:.4f} | MAPE : {mape_rlb:.2f}% | R² : {r2_rlb:.4f}")
print(f"    Status: {'✅ Sangat Baik' if mape_rlb < 10 else '✅ Baik'}")

# ── RF: Prediksi Berat 7 Hari ke Depan ───────────────────
# Target = berat rata-rata 7 hari ke depan (lebih realistis)
rf_rows = []
for batch in df['Batch'].unique():
    batch_df = df[df['Batch'] == batch].sort_values('Hari').reset_index(drop=True)
    for i, row in batch_df.iterrows():
        # Target: berat 7 hari ke depan
        future_idx = min(i + 7, len(batch_df) - 1)
        berat_future = batch_df.loc[future_idx, 'Berat_Ratarata_Gram']
        rf_rows.append({
            'Hari': row['Hari'],
            'Populasi_Pagi': row['Populasi_Pagi'],
            'Mortalitas_Kumulatif': row['Mortalitas_Kumulatif'],
            'Berat_Ratarata_Gram': row['Berat_Ratarata_Gram'],
            'fase_encoded': row['fase_encoded'],
            'target_berat_7hari': berat_future,
        })

rf_df = pd.DataFrame(rf_rows)

X_rf = rf_df[['Hari', 'Populasi_Pagi', 'Mortalitas_Kumulatif',
               'Berat_Ratarata_Gram', 'fase_encoded']].values
y_rf = rf_df['target_berat_7hari'].values

X_train_f, X_test_f, y_train_f, y_test_f = train_test_split(
    X_rf, y_rf, test_size=0.2, random_state=42)

scaler_rf = StandardScaler()
X_train_fs = scaler_rf.fit_transform(X_train_f)
X_test_fs  = scaler_rf.transform(X_test_f)

print("\n[2] Training Random Forest (estimasi berat 7 hari ke depan)...")
rf = RandomForestRegressor(
    n_estimators=200,
    max_depth=15,
    min_samples_split=5,
    min_samples_leaf=2,
    random_state=42,
    n_jobs=-1
)
rf.fit(X_train_fs, y_train_f)
yf_pred = rf.predict(X_test_fs)
mape_rf  = mean_absolute_percentage_error(y_test_f, yf_pred) * 100
r2_rf    = r2_score(y_test_f, yf_pred)
rmse_rf  = np.sqrt(mean_squared_error(y_test_f, yf_pred))
print(f"    RMSE : {rmse_rf:.4f} | MAPE : {mape_rf:.2f}% | R² : {r2_rf:.4f}")
print(f"    Status: {'✅ Sangat Baik' if mape_rf < 10 else '✅ Baik' if mape_rf < 20 else '⚠️ Cukup'}")

# Simpan
os.makedirs('models_saved', exist_ok=True)
joblib.dump(rlb,       'models_saved/model_rlb.pkl')
joblib.dump(rf,        'models_saved/model_rf.pkl')
joblib.dump(scaler_rlb,'models_saved/scaler_rlb.pkl')
joblib.dump(scaler_rf, 'models_saved/scaler_rf.pkl')

# Simpan info target RF untuk dipakai di endpoint
import json
json.dump({'rf_target': 'berat_7hari_ke_depan'},
          open('models_saved/model_info.json', 'w'))

print("\n✅ 4 file model + info tersimpan di models_saved/")
print("   RLB → prediksi total pakan harian (kg)")
print("   RF  → estimasi berat ayam 7 hari ke depan (g)")