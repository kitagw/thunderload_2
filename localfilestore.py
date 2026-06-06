import json
import os

from kivy.utils import platform

from config import Config
from fileinfo import FileInfo
from log import Log
from progressmanager import ProgressManager

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
            self.files = [FileInfo(data=f) for f in files_data]
            # 進捗ファイルを読み込む
            ProgressManager.load_progress(self.files)
            return

        # ファイルリストがなければ、ローカルファイルを読み込む
        self.files = None
        self.read_files()

    # プロパティ：ファイル数
    @property
    def file_count(self):
        return len(self.files) if self.files else 0

    # プロパティ：アップロード完了ファイル数
    @property
    def completed_file_count(self):
        return sum(1 for f in self.files if f.status == FileInfo.S_FINISHED) if self.files else 0

    # プロパティ：全体のファイルサイズ
    @property
    def file_size(self):
        return sum(fileinfo.file_size for fileinfo in self.files) if self.files else 0

    # プロパティ：全体のアップロード済のバイト位置
    @property
    def range_pos(self):
        return sum(fileinfo.range_pos for fileinfo in self.files) if self.files else 0

    # ローカルファイルを読み込む
    def read_files(self):
        # ローカルファイルの参照パス
        local_path = Config.get(Config.K_LOCAL_PATH) if platform == 'android' else '/home/kitagawa/ピクチャ:/home/kitagawa/pictures'
        # ローカルパスがなければエラー
        if not local_path:
            Log.error('設定のローカルパスが存在しません')
            return
        else:
            # ローカルパスがあれば、':'で分割して配列に代入する
            local_path_list = local_path.split(':')

        # ローカルパスリストを走査してファイル一覧からFileInfoを生成する
        files = []
        for path_item in local_path_list:
            if os.path.isdir(path_item):
                # ローカルファイル一覧読み込み
                file_count = len(files)
                files.extend([
                    FileInfo(file_dir=path_item, file_name=f)
                    for f in os.listdir(path_item)
                    if os.path.isfile(os.path.join(path_item, f))
                ])
                Log.info('読込完了：{} ({})'.format(path_item, len(files) - file_count))
            else:
                Log.warn('スキップ：{}'.format(path_item))
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

        # ファイル数、サイズのログ出力
        Log.info('読込結果：{} ファイル ({:,.1f} MB)'.format(self.file_count, FileInfo.to_view_size(self.file_size)))
