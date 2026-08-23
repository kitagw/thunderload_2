import datetime
import json
import os
import sys
import threading
import traceback

import kivy
import kivymd
from kivy.app import App
from kivy.clock import Clock
from kivy.effects.scroll import ScrollEffect
from kivy.properties import (
    ListProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.widget import Widget
from kivy.utils import escape_markup, platform
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDButton, MDButtonText
from kivymd.uix.dialog import (
    MDDialog,
    MDDialogButtonContainer,
    MDDialogContentContainer,
    MDDialogHeadlineText,
)
from kivymd.uix.label import MDLabel
from kivymd.uix.recycleview import MDRecycleView
from kivymd.uix.screen import MDScreen
from kivymd.uix.textfield import MDTextField
from kivymd.uix.widget import MDWidget

from action import Action
from appstatus import AppStatus
from config import Config
from driveclient import DriveClient
from fileinfo import FileInfo
from localfilestore import LocalFileStore
from log import Log
from progressmanager import ProgressManager
from textfield4ja import TextField_JA

# Android APIのインポート（Linux上ではエラーになるため、try-exceptで囲む）
try:
    from android.broadcast import BroadcastReceiver  # type: ignore
    from android.permissions import Permission, request_permissions  # type: ignore
    from jnius import autoclass  # type: ignore

    # Javaクラスのインポート
    String = autoclass('java.lang.String')
    # Androidクラスのインポート
    Intent = autoclass('android.content.Intent')
    IntentFilter = autoclass('android.content.IntentFilter')
    Context = autoclass('android.content.Context')
    Handler = autoclass('android.os.Handler')
    ContextCompat = autoclass('androidx.core.content.ContextCompat')
    # kivyクラスのインポート
    Service = autoclass('org.kivy.android.PythonService')
    PythonActivity = autoclass('org.kivy.android.PythonActivity')

    currentActivity = PythonActivity.mActivity

except ImportError:
    # Linux環境用のダミー
    class Dummy:
        def __getattr__(self, name): return self
    Intent, LocalBroadcastManager, PythonActivity, currentActivity, Service, IntentFilter = [Dummy()] * 6
    print("Running in desktop environment. Android APIs are mocked.")

# RecycleViewファイル項目
class FileItem(RecycleDataViewBehavior, MDBoxLayout):
    year = StringProperty()
    date = StringProperty()
    file_path = StringProperty()
    file_name = StringProperty()
    file_size = NumericProperty()
    status = StringProperty()
    try_count = NumericProperty()
    range_pos = NumericProperty()

    def refresh_view_attrs(self, rv, index, data):
        # 1. 自身のプロパティを更新
        # これによりkv側のバインディングが自動で発火します
        self.year = data.get(FileInfo.K_YEAR, '')
        self.date = data.get(FileInfo.K_DATE, '')
        self.file_path = data.get(FileInfo.K_FILE_PATH, '')
        self.file_name = data.get(FileInfo.K_FILE_NAME, '')
        self.file_size = data.get(FileInfo.K_FILE_SIZE, 0)
        self.status = data.get(FileInfo.K_STATUS, '')
        self.try_count = data.get(FileInfo.K_TRY_COUNT, 0)
        self.range_pos = data.get(FileInfo.K_RANGE_POS, 0)
        
        # 2. 親クラスの処理を呼ぶ（必須）
        return super().refresh_view_attrs(rv, index, data)
    
# ファイルRecycleView
class FileRecycleView(MDRecycleView):
    pass

# ファイル一覧画面（メイン画面）
class FileScreen(MDScreen):
    pass

# RecycleViewログテキスト
class LogText(MDLabel):
    pass

# ログ画面
class LogScreen(MDScreen):
    pass

# 設定タイトルテキスト
class ConfigTitleText(MDLabel):
    pass

# 設定項目テキスト
class ConfigItemText(MDLabel):
    title = StringProperty()
    key = StringProperty()

    # component初期化
    def on_kv_post(self, *args, **kwargs):
        super().on_kv_post(*args, **kwargs)
        self.text = self.get_config_item_text(self.title, self.key)

    # 設定項目文字の取得
    def get_config_item_text(self, title, key):
        return '[ref={}][u][b]{}[/b][/u]\n{}[/ref]'.format(key, title, Config.get(key))

    # 設定項目編集ダイアログ表示
    def show_input_dialog(self):
        # キャンセル押下
        def on_release_cancel(button):
            # ダイアログを閉じる
            self.dialog.dismiss()

        # OK押下
        def on_release_ok(button):
            # 設定内容を保存
            Config.set(self.key, self.textfield.text)
            # 画面の設定テキストを更新
            self.text = self.get_config_item_text(self.title, self.key)
            # ダイアログを閉じる
            self.dialog.dismiss()

        # 設定ロック中は変更不可
        if Config.islock():
            return

        # ダイアログ構築、表示
        self.textfield = self.get_text_field()
        self.dialog = MDDialog(
            MDDialogHeadlineText(
                text=self.title,
                halign='left',
            ),
            MDDialogContentContainer(
                self.textfield,
                orientation='vertical',
            ),
            MDDialogButtonContainer(
                Widget(),
                MDButton(
                    MDButtonText(text='キャンセル'),
                    style='text',
                    on_release=on_release_cancel
                ),
                MDButton(
                    MDButtonText(text='OK'),
                    style='text',
                    on_release=on_release_ok
                ),
            ),
        )
        self.dialog.open()
    
    # MDTextFieldでテキストフィールド生成
    def get_text_field(self):
        return MDTextField(
            text=Config.get(self.key),
            mode='outlined',
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
        )

# 設定項目テキスト（日本語入力対応版）
class ConfigItemTextJA(ConfigItemText):
    # TextField_JAでテキストフィールド生成
    def get_text_field(self):
        return TextField_JA(
            text=Config.get(self.key),
            mode='outlined',
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
        )

# 設定画面
class ConfigScreen(MDScreen):
    client = ObjectProperty()

    # トップバーロックボタン押下
    def on_release_lock(self):
        Config.change_lock()
        if Config.islock():
            self.ids.lock_button.icon = 'lock'
        else:
            self.ids.lock_button.icon = 'lock-open-alert'

    # トップバートークンファイル削除ボタン押下
    def on_release_delete_token(self):
        # キャンセル押下
        def on_release_cancel(button):
            self.delete_token_dialog.dismiss()

        # OK押下
        def on_release_ok(button):
            self.delete_token_dialog.dismiss()
            Clock.schedule_once(lambda dt: self.client.delete_token(), 0.1)

        # ダイアログ構築、表示
        self.delete_token_dialog = MDDialog(
            MDDialogHeadlineText(
                text='トークンファイルを削除して再認証します',
                halign='left',
            ),
            MDDialogButtonContainer(
                Widget(),
                MDButton(
                    MDButtonText(text='キャンセル'),
                    style='text',
                    on_release=on_release_cancel
                ),
                MDButton(
                    MDButtonText(text='OK'),
                    style='text',
                    on_release=on_release_ok
                ),
            ),
        )
        self.delete_token_dialog.open()

    # トップバーExitボタン押下
    def on_release_exit(self):
        # キャンセル押下
        def on_release_cancel(button):
            self.exit_dialog.dismiss()

        # OK押下
        def on_release_ok(button):
            os._exit(0)

        # ダイアログ構築、表示
        self.exit_dialog = MDDialog(
            MDDialogHeadlineText(
                text='Thunderload を終了します',
                halign='left',
            ),
            MDDialogButtonContainer(
                Widget(),
                MDButton(
                    MDButtonText(text='キャンセル'),
                    style='text',
                    on_release=on_release_cancel
                ),
                MDButton(
                    MDButtonText(text='OK'),
                    style='text',
                    on_release=on_release_ok
                ),
            ),
        )
        self.exit_dialog.open()

# AndroidのKivyMDを完全に騙す、バウンドしないカスタムエフェクト
class NoBoundScrollEffect(ScrollEffect):
    def convert_overscroll(self, *args, **kwargs):
        return 0  # オーバースクロール（バウンド量）を常にゼロにする

class ThunderloadWidget(MDWidget):
    # component初期化
    def on_kv_post(self, *args, **kwargs):
        super().on_kv_post(*args, **kwargs)

        # ターゲットにするRecycleViewのリスト
        rv_list = [
            self.ids.file_screen.ids.rv,
            self.ids.log_screen.ids.rv
        ]
        # デフォルトの StretchOverScroll 系のバウンド機能を無効化する
        for rv in rv_list:
            rv.effect_cls = NoBoundScrollEffect

        # ログハンドラ設定
        Log.set_handler(self.add_log, '●')
        # バージョン情報
        Log.info('バージョン情報：\n- Python {}\n- Kivy {}\n- KivyMD {}'.format(sys.version.split()[0], kivy.__version__, kivymd.__version__))

        # AppStatusのハンドラ設定
        AppStatus.set_handler(self.update_screen_by_appstatus)
        # DriveClient初期化
        try:
            self.client = DriveClient()
            # 設定画面にDriveClientを設定
            self.ids.config_screen.client = self.client
            Log.info('DriveClient初期化完了')
        except Exception as ex:
            Log.error('DriveClient初期化失敗\n' + repr(ex))
            return

        # レシーバー登録
        self.regist_broadcast_receiver()
        # 権限リクエスト
        self.request_permissions()

    # 権限リクエスト（通知、写真と動画の権限）
    def request_permissions(self):
        if platform == 'android':
            request_permissions([
                Permission.POST_NOTIFICATIONS,
                Permission.READ_MEDIA_IMAGES,
                Permission.READ_MEDIA_VIDEO
            ], self.on_permissions_result)
        else:
            # Linux環境では権限リクエストは不要なので、直接コールバックを呼び出して画面を初期化する
            self.on_permissions_result(None, None)

    # 権限リクエストの結果コールバック
    def on_permissions_result(self, permissions, grant_results):
        # UI スレッド外から呼ばれた場合は UI スレッドで実行する
        if threading.current_thread() is not threading.main_thread():
            Clock.schedule_once(lambda dt: self.on_permissions_result(permissions, grant_results), 0)
            return

        # ローカルファイルストア初期化
        self.file_store = LocalFileStore()
        # ローカルファイルが無効（変更あり）の場合で、AppStatusが完了、または、エラーの場合はリフレッシュ
        if not self.file_store.valid and AppStatus.get_status() in (AppStatus.S_COMPLETE, AppStatus.S_ERROR):
            self.on_release_refresh()
        else:
            # リフレッシュしない場合は、ファイルスクリーンの初期化のみ
            self.init_file_screen()

        # 現在のAppStatusに応じて画面を更新
        self.update_screen_by_appstatus()

        # 実行中、もしくは、停止中であればサービスを開始する
        match AppStatus.get_status():
            case AppStatus.S_RUNNING | AppStatus.S_STOPPING:
                Log.info('サービスを再開します')
                # サービス開始
                Clock.schedule_once(self.start_service, 0)
            case _:
                pass
            
    # ファイルスクリーン初期化
    def init_file_screen(self):
        # ファイル一覧を一度クリア
        # （クリアしないと、同一データでのリフレッシュ後、進捗更新時に画面が更新されなくなる）
        self.ids.file_screen.ids.rv.data = []
        # 画面コンポーネント初期化
        if self.file_store.file_count > 0:
            self.ids.file_screen.ids.rv.data.extend(
                file.data
                for file in self.file_store.files
            )
            self.ids.file_screen.ids.msg.text = 'ファイル数：{}'.format(self.file_store.file_count)
            Log.info('ローカルファイル読込完了')
        else:
            self.ids.file_screen.ids.msg.text = 'ファイルなし'
            Log.warn('ローカルファイルなし')

    # レシーバー登録
    def regist_broadcast_receiver(self):
        if platform == 'android':
            # 1. まずフィルターを定義
            intent_filter = IntentFilter()
            actions = [Action.APP, Action.UPDATE, Action.LOG]
            for action in actions:
                intent_filter.addAction(action)

            # 2. レシーバーを作成し、必要に応じてフィルターを適用
            self.br = BroadcastReceiver(self.on_broadcast_received, actions=actions)

            # 3. 登録
            if hasattr(self.br, 'receiver'):
                currentActivity.registerReceiver(
                    self.br.receiver, 
                    intent_filter, 
                    ContextCompat.RECEIVER_NOT_EXPORTED
                )
            Log.info('レシーバー登録完了')

    # AppStatusに応じて画面を更新
    def update_screen_by_appstatus(self):
        # AppStatusに応じて画面を更新
        Log.info('実行状態：{} ({})'.format(AppStatus.get_status(), AppStatus.get_last_status_update_time()))

        match AppStatus.get_status():
            case AppStatus.S_IDLE:
                # ドライブクライアントが有効、かつ、ファイルが存在している場合に、稲妻ボタンを活性にする
                if self.client.is_valid and self.file_store.file_count > 0:
                    # 稲妻ボタンを活性にする
                    self.ids.thunder_button.disabled = False
                    # 稲妻ボタンを黄色にする
                    self.ids.thunder_button.color = [1, 1, 0, 1]
                else:
                    # 稲妻ボタンを非活性にする
                    self.ids.thunder_button.disabled = True

                # 更新ボタン活性化する
                self.ids.file_screen.ids.refresh_button.disabled = False
                # 更新ボタンを白色にする
                self.ids.file_screen.ids.refresh_button.color = [1, 1, 1, 1]
                # インジケーター更新：黄
                # 進捗値は self.file_storeで管理している処理済サイズから算出される（レジューム時には続きからの値となる）
                self.update_progress_indicator(color=[1, 1, 0, 1])

            case AppStatus.S_RUNNING:
                # 稲妻ボタンを活性にする
                self.ids.thunder_button.disabled = False
                # 稲妻ボタンを赤色にする
                self.ids.thunder_button.color = [1, 0, 0, 1]
                # 更新ボタン非活性化
                self.ids.file_screen.ids.refresh_button.disabled = True
                # インジケーター更新：黄
                # 進捗値は self.file_storeで管理している処理済サイズから算出される（レジューム時には続きからの値となる）
                self.update_progress_indicator(color=[1, 1, 0, 1])

            case AppStatus.S_STOPPING:
                # 稲妻ボタンを非活性にする
                self.ids.thunder_button.disabled = True
                # 更新ボタン非活性化する
                self.ids.file_screen.ids.refresh_button.disabled = True
                # インジケーター更新：黄色
                # 進捗値は self.file_storeで管理している処理済サイズから算出される（レジューム時には続きからの値となる）
                self.update_progress_indicator(color=[1, 1, 0, 1])

            case AppStatus.S_STOPPED:
                # 稲妻ボタンを活性にする
                self.ids.thunder_button.disabled = False
                # 稲妻ボタンを黄色にする
                self.ids.thunder_button.color = [1, 1, 0, 1]
                # 更新ボタン活性化する
                self.ids.file_screen.ids.refresh_button.disabled = False
                # 更新ボタンを白色にする
                self.ids.file_screen.ids.refresh_button.color = [1, 1, 1, 1]
                # インジケーター更新：灰色
                # 進捗値は self.file_storeで管理している処理済サイズから算出される（レジューム時には続きからの値となる）
                self.update_progress_indicator(color=[0.5, 0.5, 0.5, 1])
                # 停止中メッセージを表示
                self.ids.file_screen.ids.msg.text = '停止中 ({}/{})'.format(self.file_store.completed_file_count, self.file_store.file_count)

            case AppStatus.S_COMPLETE:
                # 稲妻ボタンを非活性にする
                self.ids.thunder_button.disabled = True
                # 更新ボタン活性化する
                self.ids.file_screen.ids.refresh_button.disabled = False
                # 更新ボタンを白色にする
                self.ids.file_screen.ids.refresh_button.color = [1, 1, 1, 1]
                # インジケーター更新：緑
                # 進捗値は self.file_storeで管理している処理済サイズから算出される（レジューム時には続きからの値となる）
                self.update_progress_indicator(color=[0, 1, 0, 1])
                # メッセージにアップロード完了と完了日時を表示する
                self.ids.file_screen.ids.msg.text = 'アップロード完了 ({}/{})'.format(self.file_store.completed_file_count, self.file_store.file_count)

            case AppStatus.S_ERROR:
                # 稲妻ボタンを非活性にする
                self.ids.thunder_button.disabled = True
                # 更新ボタン活性化する
                self.ids.file_screen.ids.refresh_button.disabled = False
                # 更新ボタンを白色にする
                self.ids.file_screen.ids.refresh_button.color = [1, 1, 1, 1]
                # インジケーター更新：赤
                # 進捗値は self.file_storeで管理している処理済サイズから算出される（レジューム時には続きからの値となる）
                self.update_progress_indicator(color=[1, 0, 0, 1])
                # メッセージにエラー発生と日時を表示する
                self.ids.file_screen.ids.msg.text = 'エラー終了 ({}/{})'.format(self.file_store.completed_file_count, self.file_store.file_count)
            
            case _:
                pass        

    # ログ追加（UIスレッド外から呼ばれる可能性があるため、UIスレッドで実行する）
    def add_log(self, process_symbol, level, color, log_text):
        # UI スレッド外から呼ばれた場合は UI スレッドで実行する
        if threading.current_thread() is not threading.main_thread():
            Clock.schedule_once(lambda dt: self.add_log(process_symbol, level, color, log_text), 0)
            return

        date_str = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')

        self.ids.log_screen.ids.rv.data.append({
            'markup': True,
            'text': '{} &bl;{}&br; &bl;[color={}]{}[/color]&br;\n{}'.format(
                date_str, process_symbol, color, level, escape_markup(log_text),
            ),
        })

    # fileスクリーンボタン押下処理
    def on_release_file(self, bar_button):
        self.ids.sm.current = 'file'

    # logスクリーンボタン押下処理
    def on_release_log(self, bar_button):
        self.ids.sm.current = 'log'

    # configスクリーンボタン押下処理
    def on_release_config(self, bar_button):
        self.ids.sm.current = 'config'
    
    # リプレッシュボタン押下処理
    def on_release_refresh(self):
        Log.info('ファイル一覧をリフレシュします')
        # 進捗ファイルを削除
        ProgressManager.clear_progress()
        # ローカルファイルを再読込してファイルストアを更新
        self.file_store.read_files()
        # ファイルスクリーン初期化
        self.init_file_screen()
        # AppStatusをアイドルに更新
        AppStatus.set_status(AppStatus.S_IDLE)

    # スタート（稲妻）ボタン押下処理
    def on_release_start(self):
        if self.file_store.file_count == 0:
            return 

        match AppStatus.get_status():
            case AppStatus.S_IDLE:
                # AppStatusをアイドルから実行中に更新
                AppStatus.set_status(AppStatus.S_RUNNING)
                # 進捗ファイル初期化
                ProgressManager.init_progress(self.file_store.files)
                Log.info('進捗ファイルを初期化しました')
                # サービス開始
                Clock.schedule_once(self.start_service, 0)

            case AppStatus.S_STOPPED:
                # AppStatusを停止から実行中に更新
                AppStatus.set_status(AppStatus.S_RUNNING)
                # サービス開始
                Clock.schedule_once(self.start_service, 0)

            case AppStatus.S_RUNNING:
                # AppStatusを実行中から停止中に更新
                AppStatus.set_status(AppStatus.S_STOPPING)

            case _:
                pass

    # サービス開始
    def start_service(self, dt):
        if platform == 'android':
            # クラス名はマニフェストと完全に一致させる
            service_class_name = 'org.kitagw.thunderload_2.ServiceThunderloadservice'
            service_class = autoclass(service_class_name)
            service_intent = Intent(currentActivity, service_class)

            # --- 重要：KivyのPythonService(Java)が内部で必要とする全パス情報を取得 ---
            app_root = currentActivity.getFilesDir().getAbsolutePath() + "/app"
            
            # --- JNIエラー(NULL jstring)を防ぐための7つの必須Extra ---
            service_intent.putExtra(String('androidPrivate'), String(app_root))
            service_intent.putExtra(String('androidArgument'), String(app_root))
            service_intent.putExtra(String('serviceEntrypoint'), String('service/main.py'))
            service_intent.putExtra(String('pythonName'), String('thunderloadservice'))
            service_intent.putExtra(String('pythonHome'), String(app_root))
            service_intent.putExtra(String('pythonPath'), String(app_root))
            service_intent.putExtra(String('pythonServiceArgument'), String('')) # 空文字でOK

            # --- Android 14 / ForegroundServiceを動かすための設定 ---
            service_intent.putExtra(String('serviceStartAsForeground'), String('true'))
            service_intent.putExtra(String('serviceTitle'), String('Thunderload Service'))
            service_intent.putExtra(String('serviceDescription'), String('Service is running...'))

            # サービスの開始
            currentActivity.startForegroundService(service_intent)
            Log.info('サービスを開始しました')

    # broadcast受信コールバック
    def on_broadcast_received(self, context, intent):
        """ブロードキャストを受信した時のコールバック"""
        # UI スレッド外から呼ばれた場合は UI スレッドで実行する
        if threading.current_thread() is not threading.main_thread():
            Clock.schedule_once(lambda dt: self.on_broadcast_received(context, intent), 0)
            return

        # intent からデータを取り出してUIを更新
        match intent.getAction():
            case Action.APP:
                # AppStatusに応じて画面を更新
                self.update_screen_by_appstatus()

            case Action.UPDATE:
                # intent から file_no と fileinfo と event を取り出す
                file_no_str = intent.getStringExtra('file_no')
                fileinfo_json = intent.getStringExtra('fileinfo')
                event_str = intent.getStringExtra('event')
                # これらが存在する場合のみ処理を行う（サービス側でイベント発生時に送信しているはずだが、念のため）
                if file_no_str and fileinfo_json and event_str:
                    try:
                        # 文字列から必要なデータを取得
                        file_no = int(file_no_str)
                        fileinfo = FileInfo(data=json.loads(fileinfo_json))
                        event = event_str
                        
                        # ファイルアイテム更新
                        self.refresh_file_item(file_no, fileinfo)

                        # 進捗更新は、処理中のファイルに対してのみ行う（完了や失敗の更新は on_complete や on_error で行う）
                        match event:
                            case FileInfo.E_FILE_PROGRESS:
                                self.on_file_progress(file_no, fileinfo)
                            case FileInfo.E_UPLOAD_PROGRESS:
                                self.on_upload_progress(file_no, fileinfo)
                            case _:
                                pass

                    except Exception as e:
                        Log.error(traceback.format_exc())

            case Action.LOG:
                # 文字列から必要なデータを取得
                process_symbol_str = intent.getStringExtra('process_symbol')
                level_str = intent.getStringExtra('level')
                color_str = intent.getStringExtra('color')
                log_text_str = intent.getStringExtra('log_text')
                # これらが存在する場合のみ処理を行う（サービス側でログ発生時に送信しているはずだが、念のため）
                if process_symbol_str and level_str and color_str and log_text_str:
                    self.add_log(process_symbol_str, level_str, color_str, log_text_str)
            case _:
                Log.warning(f"Unknown action received: {intent.getAction()}")

    # アプリ終了時の処理
    def on_stop(self):
        # アプリ終了時にレシーバーを停止（重要）
        if platform == 'android' and hasattr(self, 'br'):
            self.br.stop()
        super().on_stop()

    # 処理中イベント処理
    def on_file_progress(self, file_no, fileinfo):
        self.ids.file_screen.ids.msg.text = 'アップロード中... ({}/{})'.format(file_no, self.file_store.file_count)

    # アップロード中イベント処理
    def on_upload_progress(self, file_no, fileinfo):
        # インジケーター更新
        self.update_progress_indicator()

    # ファイルアイテム更新
    def refresh_file_item(self, file_no, fileinfo):
        # file_no は 1-origin なので -1 してアクセス
        index = file_no - 1
        # fileinfo でファイルストアの該当ファイルを更新
        self.file_store.files[index].update_from(fileinfo)
        # RecycleViewの該当アイテムを更新
        rv = self.ids.file_screen.ids.rv
        rv.data[index] = {}
        rv.data[index] = fileinfo.data

    # インジケーター更新
    def update_progress_indicator(self, color=None):
        # 進捗値は self.file_storeで管理している処理済サイズから算出される（レジューム時には続きからの値となる）
        app = App.get_running_app()
        if self.file_store.file_size > 0:
            app.progress_value = self.file_store.range_pos / self.file_store.file_size * 100
        else:
            app.progress_value = 0
        # 進捗ログ出力
        Log.info(f"[✓] {self.file_store.range_pos:,} / {self.file_store.file_size:,} ({app.progress_value:.2f}%)")
        # 色
        if color is not None:
            app.progress_color = color

# Thunderloadアプリクラス
class ThunderloadApp(MDApp):
    # アプリ全体で共有する進捗プロパティ
    progress_value = NumericProperty(0)
    progress_color = ListProperty([1, 1, 0, 1])

    # コンストラクタ
    def __init__(self, **kwargs):
        super(ThunderloadApp, self).__init__(**kwargs)
        self.title = 'Thunderload'
        self.theme_cls.theme_style = 'Dark'
