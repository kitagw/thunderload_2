import os
import json
from kivy.utils import platform
from fileinfo import FileInfo
from log import Log

'''
進捗管理クラス
進捗の管理方法：
- 進捗は、バックログ、処理中、完了の3つのステータスで管理する
- 進捗は、バックログ、処理中、完了の3つのフォルダに分けて管理する
- 進捗のファイルは、ユニークなIDをファイル名とする
- 進捗の更新日時は、ファイルの更新日時を使用する
- 進捗の内容は、ファイルの中身を使用する
- 進捗の移動は、ファイルの移動で行う
- 進捗の削除は、ファイルの削除で行う
進捗のステータスの命名規則：
- バックログ：backlog
- 処理中：processing
- 完了：done
'''
class ProgressManager():
    # クラス変数：初期化フラグ
    _initialized = False

    K_PROGRESS_BASE = 'PROGRESS_BASE'
    K_BACKLOG = 'BACKLOG'
    K_PROCESSING = 'PROCESSING'
    K_DONE = 'DONE'

    items = {}

    @classmethod
    def _initialize_static(cls):
        # 静的初期化は、最初のアクセス時に一度だけ行う
        if cls._initialized:
            return

        # ベースとなるパスの決定
        if platform == 'android':
            BASE = os.environ['ANDROID_PRIVATE']
            if BASE.endswith('/app'):
                BASE = os.path.dirname(BASE) # これで1つ上の /files フォルダに戻る
        else:
            BASE = '/home/kitagawa/onedrive/vscode/python/thunderload_2/resources'

        # 各ステータス用フォルダのパス
        cls.items[cls.K_PROGRESS_BASE] = os.path.join(BASE, 'progress')
        cls.items[cls.K_BACKLOG] = os.path.join(cls.items[cls.K_PROGRESS_BASE], 'backlog')
        cls.items[cls.K_PROCESSING] = os.path.join(cls.items[cls.K_PROGRESS_BASE], 'processing')
        cls.items[cls.K_DONE] = os.path.join(cls.items[cls.K_PROGRESS_BASE], 'done')

        # 各ステータス用フォルダが存在しない場合は作成する
        for p in cls.items.values():
            if not os.path.exists(p):
                os.makedirs(p, exist_ok=True)

        # 静的初期化完了フラグを立てる
        cls._initialized = True

    # 取得
    @classmethod
    def get(cls, key):
        return cls.items[key] if key in cls.items else ''

    # 進捗ファイルを初期化
    @classmethod
    def init_progress(cls, files):
        # progressフォルダのbacklog、processing、doneの進捗ファイルを初期化する
        for folder in [cls.K_BACKLOG, cls.K_PROCESSING, cls.K_DONE]:
            folder_path = cls.get(folder)
            # フォルダ内のファイルを削除する
            for f in os.listdir(folder_path):
                file_path = os.path.join(folder_path, f)
                if os.path.isfile(file_path):
                    os.remove(file_path)

        # アップロード対象のファイルの名称で、backlogフォルダに空ファイルを作成する
        for f in files:
            with open(os.path.join(cls.get(cls.K_BACKLOG), f.file_name), 'w') as f2:
                pass

        # アップロード対象のファイルリストを、progressフォルダにfilelist.jsonとして保存する
        with open(os.path.join(cls.get(cls.K_PROGRESS_BASE), 'filelist.json'), 'w') as f2:
            json.dump([f.data for f in files], f2, indent=2, ensure_ascii=False)

    # 進捗ファイルを読み込む
    @classmethod
    def load_progress(cls, files):
        # backlog、processing、doneの進捗ファイルの存在状況から進捗（FileInfo.K_STATUS）を初期化する
        for f in files:
            if os.path.exists(os.path.join(cls.get(cls.K_BACKLOG), f.file_name)):
                f.status = FileInfo.S_UNPROCESSED
            elif os.path.exists(os.path.join(cls.get(cls.K_PROCESSING), f.file_name)):
                f.status = FileInfo.S_PROCESSING
            elif os.path.exists(os.path.join(cls.get(cls.K_DONE), f.file_name)):
                f.status = FileInfo.S_FINISHED
                f.range_pos = f.file_size # アップロード済のバイト位置はファイルサイズと同じにする
            else:
                f.status = FileInfo.S_UNPROCESSED

    # 進捗ファイルを削除する
    @classmethod
    def clear_progress(cls):
        # progressフォルダのfilelist.jsonを削除する
        filelist_path = os.path.join(cls.get(cls.K_PROGRESS_BASE), 'filelist.json')
        if os.path.exists(filelist_path):
            os.remove(filelist_path)
        # progressフォルダのbacklog、processing、doneの進捗ファイルを削除する
        for folder in [cls.K_BACKLOG, cls.K_PROCESSING, cls.K_DONE]:
            folder_path = cls.get(folder)
            for f in os.listdir(folder_path):
                file_path = os.path.join(folder_path, f)
                if os.path.isfile(file_path):
                    os.remove(file_path)

    # 進捗ファイルの状態を各フォルダのファイル数でログ出力する
    @classmethod
    def log_progress(cls):
        backlog_count = len(os.listdir(cls.get(cls.K_BACKLOG)))
        processing_count = len(os.listdir(cls.get(cls.K_PROCESSING)))
        done_count = len(os.listdir(cls.get(cls.K_DONE)))
        Log.info('進捗ファイル：{} / {} / {}'.format(backlog_count, processing_count, done_count))

    # 進捗ファイルをbacklogからprocessingに移動する
    @classmethod
    def transition_backlog_to_processing(cls, fileinfo):
        backlog_path = os.path.join(cls.get(cls.K_BACKLOG), fileinfo.file_name)
        processing_path = os.path.join(cls.get(cls.K_PROCESSING), fileinfo.file_name)
        if os.path.exists(backlog_path):
            os.rename(backlog_path, processing_path)

    # 進捗ファイルをprocessingからdoneに移動する
    @classmethod
    def transition_processing_to_done(cls, fileinfo):
        processing_path = os.path.join(cls.get(cls.K_PROCESSING), fileinfo.file_name)
        done_path = os.path.join(cls.get(cls.K_DONE), fileinfo.file_name)
        if os.path.exists(processing_path):
            os.rename(processing_path, done_path)

# 静的初期化
ProgressManager._initialize_static()
