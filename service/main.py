from jnius import autoclass # type: ignore
import time
from time import sleep
from service.thunderloadservice import ThunderloadService

# Javaクラスのインポート
Log = autoclass('android.util.Log')

TAG = 'SERVICE_DEBUG'

Log.i(TAG, "===== Service Python Script is Starting! =====")

tService = ThunderloadService()

try:
    # ここにこれまでのレシーバー登録処理などを記述
    Log.i(TAG, "Initializing Receiver...")
    
    start_time = int(time.time())
    counter = 0

    tService.update_notification(counter)
    tService.run_upload()

    # while True:
    #     # 10秒ごとに通知を更新
    #     if counter % 10 == 0:
    #         tService.log("Updating notification: counter={}".format(counter))
    #         tService.update_notification(counter)

    #     Log.i(TAG, "Service heartbeat...")
    #     # ここでメインアプリにデータを送る
    #     tService.send_broadcast(start_time, counter)

    #     counter += 1

    tService.log("Service is running. Waiting for 30 seconds before stopping...")
    time.sleep(30)
    tService.log("30 seconds have passed. Stopping service now.")

except Exception as e:
    Log.e(TAG, "Service crashed: " + str(e))
    tService.log("Service crashed: " + str(e)) if tService else None
finally:
    # 3. 何があっても（エラーが起きても）最後はCPUを解放する
    tService.stop_service() if tService else None
