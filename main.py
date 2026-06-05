from m5stack import *
from m5ui import *
from uiflow import *
import time
from machine import Pin, I2C 

# I2Cの初期設定
i2c = I2C(0, sda=Pin(21), scl=Pin(22), freq=100000)

print("---電流計システム開始---")

def read_ads1115_ch0():
    config_bytes = b"\xC5\x83"
    try:
        i2c.writeto_mem(0x48, 1, config_bytes)
        time.sleep_ms(20)
        raw_data = i2c.readfrom_mem(0x48, 0, 2)
        
        val = (raw_data[0] << 8) | raw_data[1]
        if val > 32767:
            val -= 65536
        return val
    except:
        return None

# =======================================================
# ✨ 自動ゼロ点調整（オートキャリブレーション）
# =======================================================
print("ゼロ点調整中...（電流を流さないでください）")
time.sleep(0.5)

valid_samples = 0
total_voltage = 0

# 最初に50回正しく読めたデータの平均値を計算する
while valid_samples < 50:
    raw = read_ads1115_ch0()
    if raw is not None:
        # 62.5e-6 を掛けて2倍し、センサーの生電圧にする
        v = raw * 62.5e-6 * 2.0
        total_voltage += v
        valid_samples += 1
        print(".", end="")
    time.sleep_ms(50)
print("done.")

# これがこの環境における「本物の0Aのときの電圧」になります
zero_voltage = total_voltage / 50
print("調整完了！ 0A時の電圧: {:.3f}V".format(zero_voltage))
print("")

# =======================================================
# メインループ（移動平均フィルター付き）
# =======================================================
history = [] # 過去のデータを溜めるリスト

while True:
    raw_value = read_ads1115_ch0()
    if raw_value is None:
        time.sleep(0.2)
        continue
        
    # 過去5回分のRaw値を記憶する
    history.append(raw_value)
    if len(history) > 5:
        del history[0] # 古いデータを捨てる
        
    # リストの平均値を今回のRaw値として採用する
    avg_raw = sum(history) / len(history)
        
    # 平均値を使って電圧と電流を計算
    ads_voltage = avg_raw * 62.5e-6
    sensor_voltage = ads_voltage * 2.0
    current = (sensor_voltage - zero_voltage) / 0.06781

    # 0.1 のノイズカット
    if -0.1 < current < 0.1:
        current = 0.0
  
    # 表示用に実際の int型 に戻して表示
    print("Raw: {:5d} | ADS_V: {:.3f}V | Sens_V: {:.3f}V | 電流: {:.2f} A".format(
        int(avg_raw), ads_voltage, sensor_voltage, current))
  
    time.sleep(0.2)

