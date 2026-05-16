import traceback
from jnius import autoclass # type: ignore
from log import Log
from service.thunderloadservice import ThunderloadService

tService = None

try:
    # サービスのインスタンスを作成
    tService = ThunderloadService()
    # ロガーのハンドラーをサービスのsend_logメソッドに設定
    Log.handler(tService.send_log, '◎')
    # サービスのアップロード処理を開始
    tService.run_upload()
except Exception as e:
    Log.error(traceback.format_exc())
finally:
    # 3. 何があっても（エラーが起きても）最後はCPUを解放する
    tService.stop_service() if tService else None
