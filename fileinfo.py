import datetime
import os

from PIL import Image, UnidentifiedImageError

'''
ファイル情報クラス
インスタンスデータは全て辞書型に保持する。
'''
class FileInfo:
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
        self.data[FileInfo.K_FILE_PATH] = file_path
        self.data[FileInfo.K_FILE_NAME] = file_name
        # ファイルサイズ
        self.data[FileInfo.K_FILE_SIZE] = os.path.getsize(file_path)
        # ファイル撮影日情報（または更新日j）
        mdatetime = FileInfo.get_mdatetime(file_path, file_name)
        self.data[FileInfo.K_YEAR] = mdatetime.strftime('%Y')
        self.data[FileInfo.K_DATE] = mdatetime.strftime('%Y%m%d_')
        # 初期状態
        self.data[FileInfo.K_STATUS] = FileInfo.S_UNPROCESSED
        # 試行回数
        self.data[FileInfo.K_TRY_COUNT] = 0
        # バイト位置
        self.data[FileInfo.K_RANGE_POS] = 0

    # プロパティ：ファイルパス
    @property
    def file_path(self):
        return self.data[FileInfo.K_FILE_PATH]
    
    # プロパティ：ファイル名
    @property
    def file_name(self):
        return self.data[FileInfo.K_FILE_NAME]
    
    # プロパティ：ファイルサイズ
    @property
    def file_size(self):
        return self.data[FileInfo.K_FILE_SIZE]
    
    # プロパティ：更新年
    @property
    def year(self):
        return self.data[FileInfo.K_YEAR]

    # プロパティ：更新日
    @property
    def date(self):
        return self.data[FileInfo.K_DATE]

    # プロパティ：アップロードの状態
    @property
    def status(self):
        return self.data[FileInfo.K_STATUS]
    @status.setter
    def status(self, value):
        self.data[FileInfo.K_STATUS] = value

    # プロパティ：試行回数
    @property
    def try_count(self):
        return self.data[FileInfo.K_TRY_COUNT]
    @try_count.setter
    def try_count(self, value):
        self.data[FileInfo.K_TRY_COUNT] = value

    # プロパティ：アップロード済のバイト位置
    @property
    def range_pos(self):
        return self.data[FileInfo.K_RANGE_POS]
    @range_pos.setter
    def range_pos(self, value):
        self.data[FileInfo.K_RANGE_POS] = value

    # FileInfoを別のFileInfoから更新する
    def update_from(self, other):
        self.data.update(other.data)

    # 状態遷移：処理中
    def to_stat_progress(self, try_count):
        self.status = FileInfo.S_PROCESSING
        self.try_count = try_count
        self.range_pos = 0

    # 状態遷移：完了
    def to_stat_successful(self):
        self.status = FileInfo.S_FINISHED

    # 状態遷移：失敗
    def to_stat_failed(self):
        self.status = FileInfo.S_FAILED

    # アップロード中
    def uploading(self, pos):
        self.range_pos = pos

    # ファイルの更新日取得
    @classmethod
    def get_mdatetime(cls, file_path, file_name):
        '''
        取得優先順
        1. ファイル名先頭8文字
        2. 画像ファイルEXIFのDateTimeOriginal(36867)属性
        3. 画像ファイルEXIFのDateTime(306)属性
        4. ファイルのタイムスタンプ
        '''
        # 1. ファイル名先頭8文字
        try:
            if len(file_name) >= 8:
                return datetime.datetime.strptime(file_name[:8] , '%Y%m%d')
        except ValueError:
            pass

        # 2. 画像ファイルEXIFのDateTimeOriginal(36867)属性
        try:
            # 古いPillow向けに代替処理を用意する
            class IFD:
                Exif = 34665

            date_time_original = Image.open(file_path).getexif().get_ifd(IFD.Exif).get(36867)
            if date_time_original:
                return datetime.datetime.strptime(date_time_original, '%Y:%m:%d %H:%M:%S')
        except UnidentifiedImageError as ex:
            pass

        # 3. 画像ファイルEXIFのDateTime(306)属性
        try:
            date_time = Image.open(file_path).getexif().get(306)
            if date_time:
                return datetime.datetime.strptime(date_time, '%Y:%m:%d %H:%M:%S')
        except UnidentifiedImageError as ex:
            pass

        # 4. ファイルのタイムスタンプ
        return datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
    
    # 表示用ファイルサイズ（MByte表記、最低0.1とする）
    @classmethod
    def to_view_size(cls, size):
        if size == 0:
            return 0
        m_size = size / FileInfo.MBYTE_SIZE
        return 0.1 if m_size < 0.1 else m_size
