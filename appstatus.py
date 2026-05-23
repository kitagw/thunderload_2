import json
import os
from kivy.utils import platform 

class AppStatus:
    # 辞書キー
    # ：設定保管先のファイルパス
    JSON_PATH = None
    # ：実行状態
    K_EXEC_STATUS = 'exec_status'
    # ：メッセージ
    K_MESSAGE = 'message'
    # ：最終更新日時
    K_LAST_UPDATE = 'last_update'

    # 設定項目
    items = None

    # 実行状態の定数
    # ：アイドル状態
    S_EXEC_STATUS_IDLE = 'idle'
    # ：実行中状態
    S_EXEC_STATUS_RUNNING = 'running'
    # ：停止待ち状態
    S_EXEC_STATUS_STOPPING = 'stopping'
    # ：停止状態
    S_EXEC_STATUS_STOPPED = 'stopped'
    # ：完了状態
    S_EXEC_STATUS_COMPLETED = 'completed'
    # ：エラー状態
    S_EXEC_STATUS_ERROR = 'error'

    @classmethod
    def _initialize_static(cls):
        # ベースとなるパスの決定
        if platform == 'android':
            BASE = os.environ['ANDROID_PRIVATE']
            if BASE.endswith('/app'):
                BASE = os.path.dirname(BASE) # これで1つ上の /files フォルダに戻る
        else:
            BASE = '/home/kitagawa/onedrive/vscode/python/thunderload_2/resources'

        AppStatus.JSON_PATH = os.path.join(BASE, 'app_status.json')

    # 取得（ファイルから取得）
    def get(key):
        if os.path.isfile(AppStatus.JSON_PATH):
            # app_statusファイルがローカルにある場合はロード
            jsondata = open(AppStatus.JSON_PATH,'r')
            AppStatus.items = json.load(jsondata)
        else:
            AppStatus.items = json.loads('{}')

        return AppStatus.items[key] if key in AppStatus.items else ''

    # 設定（ファイルに書き込み）
    def set(key, value):
        AppStatus.items[key]=value
        # ファイルに保存
        with open(AppStatus.JSON_PATH, 'w') as f2:
            json.dump(AppStatus.items, f2, indent=2)

AppStatus._initialize_static()
