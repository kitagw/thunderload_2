#-*- coding: utf-8 -*-

'''
ローカルファイル管理
'''
import datetime
import json
import os
from config import Config
from kivy.utils import platform 
from log import Log
from PIL import Image, UnidentifiedImageError
from progressmanager import ProgressManager

'''
ファイルの状態
インスタンスデータは全て辞書型に保持する。
'''
class FileStat:
    # 辞書キー
    # ：ファイルパス
    K_FILE_PATH = 'file_path'
    # ：ファイル名
    K_FILE_NAME = 'file_name'
    # ：ファイルサイズ
    K_FILE_SIZE = 'file_size'
    # ：撮影（更新）年
    K_YEAR = 'year'
    # ：撮影（更新）日
    K_DATE = 'date'
    # ：アップロードの状態（UNPROCESSED, PROCESSING, FINISHED, FAILED）
    K_STATUS = 'status' 
    # ：試行回数
    K_TRY_COUNT = 'try_count'
    # ：アップロード済のバイト位置
    K_RANGE_POS = 'range_pos'

    # アップロードの状態
    # ：未処理
    S_UNPROCESSED = 'UNPROCESSED'
    # ：処理中
    S_PROCESSING = 'PROCESSING'
    # ：完了
    S_FINISHED = 'FINISHED'
    # ：失敗
    S_FAILED = 'FAILED'

    # イベント
    # ：ファイル処理の進捗
    E_FILE_PROGRESS = 'FILE_PROGRESS'
    # ：アップロードの進捗
    E_UPLOAD_PROGRESS = 'UPLOAD_PROGRESS'
    # ：ファイル処理の完了
    E_COMPLETED = 'COMPLETED'
    # ：エラー
    E_ERROR = 'ERROR'

    # 1MByteのサイズ
    MBYTE_SIZE = 1048576 #1Mbyte

    # コンストラクタ
    def __init__(self, file_dir=None, file_name=None, data=None):
        # インスタンスデータの初期化
        if data is None:
            self.data = {}
        else:
            self.data = data
            return

        # ファイル名、パス情報
        file_path = f'{file_dir}/{file_name}'
        self.data[FileStat.K_FILE_PATH] = file_path
        self.data[FileStat.K_FILE_NAME] = file_name
        # ファイルサイズ
        self.data[FileStat.K_FILE_SIZE] = os.path.getsize(file_path)
        # ファイル撮影日情報（または更新日j）
        mdatetime = FileStat.get_mdatetime(file_path, file_name)
        self.data[FileStat.K_YEAR] = mdatetime.strftime('%Y')
        self.data[FileStat.K_DATE] = mdatetime.strftime('%Y%m%d_')
        # 初期状態
        self.data[FileStat.K_STATUS] = FileStat.S_UNPROCESSED
        self.data[FileStat.K_TRY_COUNT] = 0
        self.data[FileStat.K_RANGE_POS] = 0

    # プロパティ：ファイルパス
    @property
    def file_path(self):
        return self.data[FileStat.K_FILE_PATH]
    
    # プロパティ：ファイル名
    @property
    def file_name(self):
        return self.data[FileStat.K_FILE_NAME]
    
    # プロパティ：ファイルサイズ
    @property
    def file_size(self):
        return self.data[FileStat.K_FILE_SIZE]
    
    # プロパティ：更新年
    @property
    def year(self):
        return self.data[FileStat.K_YEAR]

    # プロパティ：更新日
    @property
    def date(self):
        return self.data[FileStat.K_DATE]

    # プロパティ：アップロードの状態
    @property
    def status(self):
        return self.data[FileStat.K_STATUS]

    # プロパティ：アップロード済のバイト位置
    @property
    def range_pos(self):
        return self.data[FileStat.K_RANGE_POS]

    # ファイルStatを別のFileStatから更新する
    def update_from(self, other):
        self.data.update(other.data)

    # 状態遷移：処理中
    def to_stat_progress(self, try_count):
        self.data[FileStat.K_STATUS] = FileStat.S_PROCESSING
        self.data[FileStat.K_TRY_COUNT] = try_count
        self.data[FileStat.K_RANGE_POS] = 0
        # backlogファイルをprocessingファイルに移動する
        backlog_path = os.path.join(ProgressManager.get(ProgressManager.K_BACKLOG), self.file_name)
        processing_path = os.path.join(ProgressManager.get(ProgressManager.K_PROCESSING), self.file_name)
        if os.path.exists(backlog_path):
            os.rename(backlog_path, processing_path)

    # 状態遷移：完了
    def to_stat_successful(self):
        self.data[FileStat.K_STATUS] = FileStat.S_FINISHED
        # processingファイルをdoneファイルに移動する
        processing_path = os.path.join(ProgressManager.get(ProgressManager.K_PROCESSING), self.file_name)
        done_path = os.path.join(ProgressManager.get(ProgressManager.K_DONE), self.file_name)
        if os.path.exists(processing_path):
            os.rename(processing_path, done_path)

    # 状態遷移：失敗
    def to_stat_failed(self):
        self.data[FileStat.K_STATUS] = FileStat.S_FAILED
    
    # アップロード中
    def uploading(self, pos):
        self.data[FileStat.K_RANGE_POS] = pos

    # ファイルの更新日取得
    @classmethod
    def get_mdatetime(cls, file_path, file_name):
        '''
        取得優先順
        1. ファイル名先頭8文字
        2. 画像ファイルEXIFの306属性
        3. ファイルのタイムスタンプ
        '''
        try:
            if len(file_name) >= 8:
                return datetime.datetime.strptime(file_name[:8] , '%Y%m%d')
        except ValueError:
            pass

        try:
            datetime306 = Image.open(file_path).getexif().get(306)
        except UnidentifiedImageError as ex:
            pass

        if datetime306:
            mdatetime = datetime.datetime.strptime(datetime306, '%Y:%m:%d %H:%M:%S')
        else:
            mdatetime = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
        return mdatetime
    
    # 表示用ファイルサイズ（MByte表記、最低0.1とする）
    @classmethod
    def to_view_size(cls, size):
        if size == 0:
            return 0
        m_size = size / FileStat.MBYTE_SIZE
        return 0.1 if m_size < 0.1 else m_size

'''
ローカルファイル保管庫
'''
class LocalFileStore:
    # コンストラクタ
    def __init__(self):
        # filelist.jsonファイルが存在する場合はそれを読み込む
        filelist_path = os.path.join(ProgressManager.get(ProgressManager.K_PROGRESS_BASE), 'filelist.json')
        if os.path.exists(filelist_path):
            with open(filelist_path, 'r') as f:
                files_data = json.load(f)
            self.files = [FileStat(data=f) for f in files_data]
            # 進捗ファイル郡を読み込む
            self.load_progress_files()
            # レジュームアップロードである
            self.resume_upload = True
            return

        # レジュームアップロードでない
        self.resume_upload = False

        # ローカルファイルの参照パス
        local_path = Config.get(Config.K_LOCAL_PATH) if platform == 'android' else '/home/kitagawa/ピクチャ:/home/kitagawa/pictures'
        Log.info('ローカルパス：{}'.format(local_path))
        # ローカルパスがなければエラー
        if not local_path:
            Log.error('設定のローカルパスが存在しません')
            return
        else:
            # ローカルパスがあれば、':'で分割して配列に代入する
            local_path_list = local_path.split(':')

        # ローカルパスリストを走査してファイル一覧からFileStatを生成する
        files = []
        for path_item in local_path_list:
            Log.info('読込開始：{}'.format(path_item))
            if os.path.isdir(path_item):
                # ローカルファイル一覧読み込み
                file_count = len(files)
                files.extend([
                    FileStat(file_dir=path_item, file_name=f)
                    for f in os.listdir(path_item)
                    if os.path.isfile(os.path.join(path_item, f))
                ])
                Log.info('読込成功：{} ({})'.format(path_item, len(files) - file_count))
            else:
                Log.warn('ディレクトリでない：{}'.format(path_item))
                continue

        # ファイル名の重複は除外する
        seen = set()
        unique_files = []
        for f in files:
            if f.file_name not in seen:
                seen.add(f.file_name)
                unique_files.append(f)

        # ファイル名でソートする
        unique_files.sort(key=lambda x: x.file_name)

        # アップロード対象のファイルリスト
        self.files = unique_files

        # ファイル数
        Log.info('アップロード対象ファイル数：{}'.format(self.file_count))
        # ファイルサイズ
        Log.info('アップロード対象ファイルサイズ：{:,.1f}MB'.format(FileStat.to_view_size(self.file_size)))

    # プロパティ：ファイル数
    @property
    def file_count(self):
        return len(self.files) if self.files else 0

    # プロパティ：全体のファイルサイズ
    @property
    def file_size(self):
        return sum(filestat.file_size for filestat in self.files) if self.files else 0

    # プロパティ：全体のアップロード済のバイト位置
    @property
    def range_pos(self):
        return sum(filestat.range_pos for filestat in self.files) if self.files else 0

    # 進捗ファイル郡を初期化
    def init_progress_files(self):
        # progressフォルダのbacklog、processing、doneの進捗ファイル郡を初期化する
        for folder in [ProgressManager.K_BACKLOG, ProgressManager.K_PROCESSING, ProgressManager.K_DONE]:
            folder_path = ProgressManager.get(folder)
            # フォルダ内のファイルを削除する
            for f in os.listdir(folder_path):
                file_path = os.path.join(folder_path, f)
                if os.path.isfile(file_path):
                    os.remove(file_path)

        # アップロード対象のファイルの名称で、backlogフォルダに空ファイルを作成する
        for f in self.files:
            with open(os.path.join(ProgressManager.get(ProgressManager.K_BACKLOG), f.file_name), 'w') as f2:
                pass

        # アップロード対象のファイルリストを、progressフォルダにfilelist.jsonとして保存する
        with open(os.path.join(ProgressManager.get(ProgressManager.K_PROGRESS_BASE), 'filelist.json'), 'w') as f2:
            json.dump([f.data for f in self.files], f2, indent=2, ensure_ascii=False)

    # 進捗ファイル郡を読み込み
    def load_progress_files(self):
        # backlog、processing、doneの進捗ファイル郡の存在状況から進捗（FileStat.K_STATUS）を初期化する
        for f in self.files:
            if os.path.exists(os.path.join(ProgressManager.get(ProgressManager.K_BACKLOG), f.file_name)):
                f.data[FileStat.K_STATUS] = FileStat.S_UNPROCESSED
            elif os.path.exists(os.path.join(ProgressManager.get(ProgressManager.K_PROCESSING), f.file_name)):
                f.data[FileStat.K_STATUS] = FileStat.S_PROCESSING
            elif os.path.exists(os.path.join(ProgressManager.get(ProgressManager.K_DONE), f.file_name)):
                f.data[FileStat.K_STATUS] = FileStat.S_FINISHED
                f.data[FileStat.K_RANGE_POS] = f.data[FileStat.K_FILE_SIZE] # アップロード済のバイト位置はファイルサイズと同じにする
            else:
                f.data[FileStat.K_STATUS] = FileStat.S_UNPROCESSED
    
    # 進捗ファイル郡の状態を各フォルダのファイル数でログ出力する
    def log_progress_files(self):
        backlog_count = len(os.listdir(ProgressManager.get(ProgressManager.K_BACKLOG)))
        processing_count = len(os.listdir(ProgressManager.get(ProgressManager.K_PROCESSING)))
        done_count = len(os.listdir(ProgressManager.get(ProgressManager.K_DONE)))
        Log.info('進捗ファイル郡の状態：backlog={}, processing={}, done={}'.format(backlog_count, processing_count, done_count))

    # 進捗ファイル郡を削除する
    def clear_progress_files(self):
        # progressフォルダのfilelist.jsonを削除する
        filelist_path = os.path.join(ProgressManager.get(ProgressManager.K_PROGRESS_BASE), 'filelist.json')
        if os.path.exists(filelist_path):
            os.remove(filelist_path)
        # progressフォルダのbacklog、processing、doneの進捗ファイル郡を削除する
        for folder in [ProgressManager.K_BACKLOG, ProgressManager.K_PROCESSING, ProgressManager.K_DONE]:
            folder_path = ProgressManager.get(folder)
            for f in os.listdir(folder_path):
                file_path = os.path.join(folder_path, f)
                if os.path.isfile(file_path):
                    os.remove(file_path)
