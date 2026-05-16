#-*- coding: utf-8 -*-

'''
クラウドストレージドライブクライアント
フォルダ作成などの処理はすべて、クラウドストレージ側の処理。
'''
import json
import os
from config import Config
from log import Log
from kivy.utils import platform 
from msal import PublicClientApplication
from office365.graph_client import GraphClient
from office365.onedrive.driveitems.driveItem import ConflictBehavior, DriveItem
from office365.runtime.client_request_exception import ClientRequestException

'''
ドライブクライアント
'''
class DriveClient():
    # Graph API スコープ
    SCOPES = ['User.Read','Files.ReadWrite.All']
    # トークン情報保管先のファイルパス
    TOKENS_JSON_PATH = None
    # 1MByteのサイズ
    MBYTE_SIZE = 1048576 #1Mbyte
    # アップロード最大試行回数
    MAX_TRY_COUNT = 9

    @classmethod
    def _initialize_static(cls):
        # ベースとなるパスの決定
        if platform == 'android':
            BASE = os.environ['ANDROID_PRIVATE']
            if BASE.endswith('/app'):
                BASE = os.path.dirname(BASE) # これで1つ上の /files フォルダに戻る
        else:
            BASE = '/home/kitagawa/onedrive/vscode/python/thunderload_2/resources'

        DriveClient.TOKENS_JSON_PATH = os.path.join(BASE, 'tokens.json')

    # コンストラクタ
    def __init__(self):
        # Graph API パラメータ
        self.client_id = Config.get(Config.K_CLIENT_ID)
        self.authority = Config.get(Config.K_AUTHORITY)
        # アップロードパス
        self.upload_path = Config.get(Config.K_UPLOAD_PATH)
        # 作成済フォルダリスト
        self.created_folders = []

        # クライアント初期化
        # Log.info('設定ファイルパス: ' + Config.CONFIG_JSON_PATH)
        if self.client_id and self.authority and self.upload_path: 
            self.__init_client()
            # Log.info('設定項目のClient_ID、authority、アップロードパスを読み込みました')
        else:
            Log.error('設定項目のClient_ID、authority、アップロードパスが登録されていません')

    # トークン削除
    def delete_token(self):
        # トークンjsonファイル削除
        os.remove(DriveClient.TOKENS_JSON_PATH)
        Log.info('トークンファイルを削除しました')
        # クライアント初期化
        self.__init_client()

    # ファイルアップロード
    def upload(self, filestat, on_upload_progress):
        # アップロード先のクラウド側のdrive_item
        drive_item = self.client.me.drive.root
        upload_path = Config.get(Config.K_UPLOAD_PATH).split('/')
        for name in upload_path:
            # アップロード先の階層まで移動
            drive_item = drive_item.get_by_path(name)

       # フォルダ初期化（無かったら作成する）
        self.__init_folder(drive_item, filestat.year, filestat.date)
        # ファイルアップロード
        remote_drive = drive_item.get_by_path(filestat.year).get_by_path(filestat.date)
        remote_drive.resumable_upload(filestat.file_path, chunk_size=DriveClient.MBYTE_SIZE *10, chunk_uploaded=on_upload_progress).execute_query()

    # クライアント初期化
    def __init_client(self):
        '''
        トークンをローカルファイルからロードする。
        ローカルにファイルがない場合は、ブラウザ認証でトークンを取得する。
        '''
        # Log.info('トークンファイル：{}'.format(DriveClient.TOKENS_JSON_PATH))
        if os.path.isfile(DriveClient.TOKENS_JSON_PATH):
            # トークンファイルがローカルにある場合はロード
            jsondata = open(DriveClient.TOKENS_JSON_PATH,'r')    
            self.tokens = json.load(jsondata)
            Log.info('リフレッシュトークンをトークンファイルからロードしました')
        else:
            Log.info('ブラウザ認証を開始します')
            # トークンファイルがない場合はブラウザ認証
            app = PublicClientApplication(
                client_id = self.client_id,
                authority = self.authority
            )
            self.tokens = app.acquire_token_interactive(
                scopes = DriveClient.SCOPES
            )
            Log.info('ブラウザ認証が完了しました')
            # 取得したトークンをローカルに保存
            with open(DriveClient.TOKENS_JSON_PATH, 'w') as f2:
                json.dump(self.tokens, f2, indent=2)
            Log.info('リフレッシュトークンをファイルに保存しました')

        # リフレッシュトークンを使ってクライアント生成
        self.client = GraphClient(self.__acquire_token_by_refresh_token)

    # リフレッシュトークンでトークン情報を取得
    def __acquire_token_by_refresh_token(self):
        # MSAL認証：リフレッシュトークンでトークン取得（アクセストークン取得が目的）
        app = PublicClientApplication(
            client_id = self.client_id,
            authority = self.authority
        )
        tokens = app.acquire_token_by_refresh_token(
            refresh_token = self.tokens['refresh_token'],
            scopes = DriveClient.SCOPES
        )
        # 取得したトークンをローカルに保存
        with open(DriveClient.TOKENS_JSON_PATH, 'w') as f2:
            json.dump(tokens, f2, indent=2)
        return tokens

    # フォルダを初期化（無かったら作成する）
    def __init_folder(self, drive_item, myear, mdate):
        '''
        フォルダは２階層分作成する。
        ex.)
          2024
           + 20240614_
        
        アップロード処理中に作成したフォルダは記憶しておき、２回作成しないようにする。
        「年/日付_」「年」の順で作成済かチェッする。
          1. 2024/20240614_
          2. 2024

        '''
        myear_mdate = myear + '/' + mdate
        # 「年/日付_」のフォルダを作成したか
        if myear_mdate not in self.created_folders:
            # 「年/」のフォルダを作成したか
            if myear not in self.created_folders:
                # 「年」フォルダを作成して作成済みリストに登録
                self.__create_folder(drive_item, myear)
                self.created_folders.append(myear)
            # 「日付_」フォルダを作成して「年/日付_」フォルダを作成済みリストに登録
            self.__create_folder(drive_item.get_by_path(myear), mdate)
            self.created_folders.append(myear_mdate)

    # フォルダを作成する
    def __create_folder(self, drive_item: DriveItem, folder_name):
        try:
            drive_item.create_folder(folder_name, ConflictBehavior.Fail).execute_query()
            Log.info('OneDriveフォルダを作成しました\n{}\n> {}'.format(drive_item.resource_path, folder_name))
        except ClientRequestException as ex:
            # すでに作成されれいた場合の例外は無視（その他の例外はスローする）
            if ex.code == 'nameAlreadyExists':
                Log.info('OneDriveフォルダは作成済でした\n{}\n> {}'.format(drive_item.resource_path, folder_name))
            else:
                raise ex

DriveClient._initialize_static()
