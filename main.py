"""
M5Stack + ADS1115 高精度電流計測システム (UIFlow 1.x / MicroPython)

【特徴】
1. UIFlowのI2C競合を回避するため、Single-shotモードで毎回手動ウェイトを入れて同期。
2. 1ビットあたり 62.5 µV (±2.048Vレンジ) の超高精度計測。
3. 起動時に50回のサンプリングを行い、ゼロ点（0A時の電圧）を自動校正。
4. 稼働中は5回の移動平均フィルターを通し、環境ノイズによるチラつきを徹底カット。
5. MicroPythonのREPLエコーバックを防ぐため、リストの削除には `del` を使用。
"""

from m5stack import *
from m5ui import *
from uiflow import *
import time
from machine import Pin, I2C 

# =======================================================
# 1. 初期設定 (I2C)
# =======================================================
# UIFlowの裏システムと衝突しないよう、速度を100kHzに落として安定化
i2c = I2C(0, sda=Pin(21), scl=Pin(22), freq=100000)

print("--- 高精度電流計システム 起動 ---")

def read_ads1115_ch0():
    """ ADS1115のCh0からRaw値を1回読み出す関数 (Single-shot) """
    # OS設定: ±2.048Vレンジ, A0ピン, Single-shotモード
    config_bytes = b"\xC5\x83"
    
    try:
        # 設定書き込み
        i2c.writeto_mem(0x48, 1, config_bytes)
        # ADS1115内部でのA/D変換完了（現像）をしっかり待つ
        time.sleep_ms(20)
        # データレジスタ(0番)から2バイト回収
        raw_data = i2c.readfrom_mem(0x48, 0, 2)
        
        # 16ビットの符号付き整数に結合
        val = (raw_data[0] << 8) | raw_data[1]
        if val > 32767:
            val -= 65536
        return val
    except:
        return None # 通信エラー時はNoneを返す

# =======================================================
# 2. 自動ゼロ点調整（オートキャリブレーション）
# =======================================================
print("ゼロ点調整中...（50サンプル取得中...）")
time.sleep(0.5)

valid_samples = 0
total_voltage = 0

while valid_samples < 50:
    raw = read_ads1115_ch0()
    if raw is not None:
        # 1bit = 62.5 µV。分圧回路(1/2)を復元するため最後に2倍する
        v = raw * 62.5e-6 * 2.0
        total_voltage += v
        valid_samples += 1
    time.sleep_ms(30)

# この環境・個体における「本物の0A時のベース電圧」を決定
zero_voltage = total_voltage / 50
print("調整完了！ 0A時の基準電圧: {:.3f}V".format(zero_voltage))
print("計測を開始します。")
print("-" * 60)

# =======================================================
# 3. メインループ（移動平均フィルター付き）
# =======================================================
history = [] # 過去のRaw値を溜めるフィルター用リスト

while True:
    raw_value = read_ads1115_ch0()
    
    if raw_value is None:
        time.sleep(0.2)
        continue
        
    # 最新の値を履歴に追加
    history.append(raw_value)
    if len(history) > 5:
        # ★重要: pop(0)は値を返してシリアルを汚すため、値を返さないdelを使用
        del history[0] 
        
    # 直近5回分の移動平均を算出（チラつきノイズの相殺）
    avg_raw = sum(history) / len(history)
        
    # 電圧・電流の計算
    ads_voltage = avg_raw * 62.5e-6  # ADS1115への入力電圧
    sensor_voltage = ads_voltage * 2.0  # 分圧前のセンサー生電圧
    current = (sensor_voltage - zero_voltage) / 0.06781  # 感度: 67.81mV/A

    # ゼロ付近の微小な揺らぎをカット（不感帯の設定）
    if -0.1 < current < 0.1:
        current = 0.0
  
    # ターミナルへ綺麗に出力
    print("Raw: {:5d} | ADS_V: {:.3f}V | Sens_V: {:.3f}V | 電流: {:.2f} A".format(
        int(avg_raw), ads_voltage, sensor_voltage, current
    ))
  
    time.sleep(0.2)