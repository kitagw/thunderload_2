from jnius import autoclass # type: ignore
import time
from time import sleep
from service.thunderloadservice import ThunderloadService

# Javaクラスのインポート
Log = autoclass('android.util.Log')

TAG = 'SERVICE_DEBUG'

Log.i(TAG, "===== Service Python Script is Starting! =====")

try:
    # ここにこれまでのレシーバー登録処理などを記述
    Log.i(TAG, "Initializing Receiver...")
    
    start_time = int(time.time())
    counter = 0

    tService = ThunderloadService()

    while True:
        # 10秒ごとに通知を更新
        if counter % 10 == 0:
            tService.log("Updating notification: counter={}".format(counter))
            tService.update_notification(counter)

        Log.i(TAG, "Service heartbeat...")
        # ここでメインアプリにデータを送る
        tService.send_broadcast(start_time, counter)

        time.sleep(1)
        counter += 1
except Exception as e:
    Log.e(TAG, "Service crashed: " + str(e))
