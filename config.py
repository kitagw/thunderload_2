import json
import os

from pathutils import get_resource_path

'''
設定管理
'''
class Config():
        # クラス変数：初期化フラグ
    _initialized = False

    # 設定保管先のファイルパス
    JSON_PATH = None
    # ローカルパス
    K_LOCAL_PATH = 'local_path'
    # アップロードパス
    K_UPLOAD_PATH = 'upload_path'
    # Client ID
    K_CLIENT_ID = 'client_id'
    # Autority
    K_AUTHORITY = 'authority'
    # 設定項目
    items = None
    # ロック状態
    lock_stat = True

    # 静的初期化
    @classmethod
    def _initialize_static(cls):
        # 静的初期化は、最初のアクセス時に一度だけ行う
        if cls._initialized:
            return

        # ベースとなるパスの決定
        cls.JSON_PATH = get_resource_path('config.json')

        if os.path.isfile(cls.JSON_PATH):
            # configファイルがローカルにある場合はロード
            jsondata = open(cls.JSON_PATH,'r')
            cls.items = json.load(jsondata)
        else:
            cls.items = json.loads('{}')

        # 静的初期化完了フラグを立てる
        cls._initialized = True

    # 取得
    @classmethod
    def get(cls, key):
        return cls.items[key] if key in cls.items else ''

    # 設定
    @classmethod
    def set(cls, key, value):
        cls.items[key]=value
        # ファイルに保存
        with open(cls.JSON_PATH, 'w') as f2:
            json.dump(cls.items, f2, indent=2)

    # ロック中か検査
    @classmethod
    def islock(cls):
        return cls.lock_stat

    # ロックステータス反転変更
    @classmethod
    def change_lock(cls):
        cls.lock_stat = not cls.lock_stat

# 静的初期化
Config._initialize_static()
