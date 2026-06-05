import datetime
import os

from kivy.utils import platform

'''
アプリケーションのステータスを定義するクラス
ステータスの管理に空ファイルを用いる
ステータスの管理方法：
- ステータスを変更する際に、対応するステータスの空ファイルを作成する
- ステータスを確認する際に、対応するステータスの空ファイルが存在するかどうかを確認する
- ステータスを変更する際に、他のステータスの空ファイルを削除する
ステータスの空ファイルの命名規則：
- ステータスの空ファイルは、ステータス名を小文字にして、拡張子を .appstatus とする
- 例：idle.appstatus, running.appstatus, stopping.appstatus, stopped.appstatus, error.appstatus, complete.appstatus
ステータスの更新日時は、空ファイルの更新日時を使用する
'''
class AppStatus:
    # クラス変数：初期化フラグ
    _initialized = False

    # *.appstatusの空ファイルを保管するベースパス
    BASE_PATH = None

    # ステータス
    # ：アイドル
    S_IDLE = "idle"
    # ：実行中
    S_RUNNING = "running"
    # ：停止中
    S_STOPPING = "stopping"
    # ：停止
    S_STOPPED = "stopped"
    # ：エラー
    S_ERROR = "error"
    # ：完了
    S_COMPLETE = "complete"

    func_send = None

    # 静的初期化
    @classmethod
    def _initialize_static(cls):
        # 静的初期化は、最初のアクセス時に一度だけ行う
        if cls._initialized:
            return
        
        # ベースとなるパスの決定
        if platform == 'android':
            cls.BASE_PATH = os.environ['ANDROID_PRIVATE']
            if cls.BASE_PATH.endswith('/app'):
                cls.BASE_PATH = os.path.dirname(cls.BASE_PATH) # これで1つ上の /files フォルダに戻る
        else:
            cls.BASE_PATH = '/home/kitagawa/onedrive/vscode/python/thunderload_2/resources'
        
        # ステータスファイルが存在しない場合は、アイドルのステータスファイルを作成する
        if not any(filename.endswith('.appstatus') for filename in os.listdir(cls.BASE_PATH)):
            cls.set_status(cls.S_IDLE)

        # 静的初期化完了フラグを立てる
        cls._initialized = True

    # ステータス変更通知のハンドラーを登録する
    @classmethod
    def set_handler(cls, func):
        cls.func_send = func

    # 現在のステータスを取得する
    @staticmethod
    def get_status():
        # ステータスの空ファイルを確認する
        # 拡張子 .appstatus を持つファイルをワイルドドカードで検索する
        for filename in os.listdir(AppStatus.BASE_PATH):
            if filename.endswith('.appstatus'):
                # ステータスの空ファイルが存在する場合は、そのステータスを返す
                return filename[:-10] # 拡張子 .appstatus を除いた部分を返す
        # ステータスの空ファイルが存在しない場合は、アイドルを返す
        return AppStatus.S_IDLE
    
    # ステータスを変更する
    @staticmethod
    def set_status(new_status):
        # ステータスの空ファイルを確認する
        for filename in os.listdir(AppStatus.BASE_PATH):
            if filename.endswith('.appstatus'):
                # ステータスの空ファイルが存在する場合は、削除する
                os.remove(os.path.join(AppStatus.BASE_PATH, filename))
        # 新しいステータスの空ファイルを作成する
        new_status_file = os.path.join(AppStatus.BASE_PATH, new_status + '.appstatus')
        with open(new_status_file, 'w') as f:
            pass # 空ファイルを作成するために、内容は書き込まない

        # ステータス変更を通知する
        if AppStatus.func_send is not None:
            AppStatus.func_send()

    # ステータスを確認する
    @staticmethod
    def is_status(status):
        # ステータスの空ファイルが存在するかどうかを確認する
        status_file = os.path.join(AppStatus.BASE_PATH, status + '.appstatus')
        return os.path.isfile(status_file)

    # ステータスの最終日時を取得する
    @staticmethod
    def get_last_status_update_time():
        # ステータスの空ファイルを確認する
        # 拡張子 .appstatus を持つファイルをワイルドドカードで検索する
        for filename in os.listdir(AppStatus.BASE_PATH):
            if filename.endswith('.appstatus'):
                # ステータスの空ファイルが存在する場合は、その更新日時を.strftime('%Y/%m/%d %H:%M:%S')でフォーマットして返す
                status_file = os.path.join(AppStatus.BASE_PATH, filename)
                dt = datetime.datetime.fromtimestamp(os.path.getmtime(status_file))
                return dt.strftime('%Y/%m/%d %H:%M:%S')
        # ステータスの空ファイルが存在しない場合は、M/Aを返す
        return 'N/A'

# 静的初期化
AppStatus._initialize_static()
