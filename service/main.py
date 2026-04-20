import time
from jnius import autoclass # type: ignore
from log import Log
from service.thunderloadservice import ThunderloadService

tService = None

try:
    tService = ThunderloadService()
    # ロガーのハンドラーをサービスのsend_logメソッドに設定
    Log.handler(tService.send_log, 'S')
    Log.info("Service is starting...")
    Log.warn("Service is starting...")
    Log.error("Service is starting...")
    start_time = int(time.time())
    counter = 0

    tService.update_notification(999)
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

    Log.info("Service is running. Waiting for 30 seconds before stopping...")
    time.sleep(30)
    Log.info("30 seconds have passed. Stopping service now.")

except Exception as e:
    Log.error("Service crashed: " + str(e)) if tService else None
finally:
    # 3. 何があっても（エラーが起きても）最後はCPUを解放する
    tService.stop_service() if tService else None
