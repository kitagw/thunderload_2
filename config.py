import json
import os
from kivy.utils import platform 

'''
設定管理
'''
class Config():
    # 設定保管先のファイルパス
    CONFIG_JSON_PATH = os.environ['ANDROID_PRIVATE'] + '/config.json' if platform == 'android' else './resources/config.json'
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

    # 取得
    def get(key):
        return Config.items[key] if key in Config.items else ''

    # 設定
    def set(key, value):
        Config.items[key]=value
        # ファイルに保存
        with open(Config.CONFIG_JSON_PATH, 'w') as f2:
            json.dump(Config.items, f2, indent=2)

    # ロック中か検査
    def islock():
        return Config.lock_stat

    # ロックステータス反転変更
    def change_lock():
        Config.lock_stat = not Config.lock_stat

# 初期化
if os.path.isfile(Config.CONFIG_JSON_PATH):
    # configファイルがローカルにある場合はロード
    jsondata = open(Config.CONFIG_JSON_PATH,'r')    
    Config.items = json.load(jsondata)
else:
    Config.items = json.loads('{}')
