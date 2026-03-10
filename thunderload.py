#-*- coding: utf-8 -*-

import datetime
import threading
import time
import os
from config import Config
from log import Log
# from driveclient import DriveClient
from filemanager import FileStat, LocalFileStore
from kivy.clock import Clock
from kivy.properties import ListProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.widget import Widget
from kivy.utils import escape_markup, platform
from kivymd.app import MDApp
from kivymd.uix.button import MDButton, MDButtonText
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.dialog import MDDialog, MDDialogHeadlineText, MDDialogButtonContainer, MDDialogContentContainer
from kivymd.uix.label import MDLabel
from kivymd.uix.recycleview import MDRecycleView
from kivymd.uix.screen import MDScreen
from kivymd.uix.textfield import MDTextField
from kivymd.uix.widget import MDWidget
from textfield4ja import TextField_JA
#import time
from time import sleep

# Android APIのインポート（Linux上ではエラーになるため、try-exceptで囲む）
try:
    from jnius import autoclass, PythonJavaClass, java_method # type: ignore
    from android.permissions import request_permissions, Permission # type: ignore
    from android.broadcast import BroadcastReceiver # type: ignore
    
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

    # カスタムアクション名
    ACTION_UPDATE = 'org.kitagw.thunderload.UPLOAD_PROGRESS_UPDATE'

except ImportError:
    # Linux環境用のダミー
    class Dummy:
        def __getattr__(self, name): return self
    Intent, LocalBroadcastManager, PythonActivity, currentActivity, Service, IntentFilter = [Dummy()] * 6
    print("Running in desktop environment. Android APIs are mocked.")

# RecycleViewファイル項目
class FileInfo(MDBoxLayout):
    year = StringProperty()
    date = StringProperty()
    file_path = StringProperty()
    file_name = StringProperty()
    file_size = NumericProperty()
    status = StringProperty()
    try_count = NumericProperty()
    range_pos = NumericProperty()

# ファイルRecycleView
class FileRecycleView(MDRecycleView):
    file_list = ListProperty()

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

class ThunderloadWidget(MDWidget):
    # component初期化
    def on_kv_post(self, *args, **kwargs):
        super().on_kv_post(*args, **kwargs)
        # ログハンドラ設定
        Log.handler(self.add_log)
        # DriveClient初期化
        try:
            Log.info('DriveClient初期化中...')
            # self.client = DriveClient()
            Log.info('DriveClient初期化完了')
        except Exception as ex:
            Log.error('DriveClient初期化失敗\n' + repr(ex))
            return
        
        # 設定画面にDriveClientを設定
        # 
        # self.ids.config_screen.client = self.client
        # 
        # ファイルスクリーン初期化
        self.init_file_screen()

    # ファイルスクリーン初期化
    def init_file_screen(self):
        # ローカルファイル読込
        self.file_store = LocalFileStore()
        # ファイル一覧を一度クリア
        # （クリアしないと、同一データでのリフレッシュ後、進捗更新時に画面が更新されなくなる）
        self.ids.file_screen.ids.rv.file_list = []
        # 画面コンポーネント初期化
        if self.file_store.file_count > 0:
            self.ids.file_screen.ids.rv.file_list.extend(
                file.data
                for file in self.file_store.files
            )
            self.ids.file_screen.ids.msg.text = 'ファイル数：{}'.format(self.file_store.file_count)
            self.ids.thunder_button.disabled = False
            Log.info('ローカルファイル読込完了')
        else:
            self.ids.file_screen.ids.msg.text = 'ファイルなし'
            self.ids.thunder_button.disabled = True
            Log.warn('ローカルファイルなし')

        # インジケーター：黄0 を App プロパティ経由で設定
        from kivy.app import App
        app = App.get_running_app()
        app.progress_color = [1, 1, 0, 1]
        app.progress_value = 0

    def add_log(self, level, color, log_text):
        print("DEBUG add_log: {}, {}, {}".format(level, color, log_text))
        # UI スレッド外から呼ばれた場合は UI スレッドで実行する
        if threading.current_thread() is not threading.main_thread():
            Clock.schedule_once(lambda dt: self.add_log(level, color, log_text), 0)
            return

        date_str = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')

        self.ids.log_screen.ids.rv.data.append({
            'markup': True,
            'text': '{} &bl;[color={}]{}[/color]&br;\n{}'.format(
                date_str, color, level, escape_markup(log_text),
            ),
        })

    def on_release_file(self, bar_button):
        self.ids.sm.current = 'file'

    def on_release_log(self, bar_button):
        self.ids.sm.current = 'log'

    def on_release_config(self, bar_button):
        self.ids.sm.current = 'config'
    
    def on_release_refresh(self):
        Log.info('ファイル一覧をリフレシュします')
        # ファイルスクリーン初期化
        self.init_file_screen()

    def on_release_start(self):
        if self.file_store.file_count == 0:
            return 

        # ボタン非活性化
        # 稲妻ボタン
        self.ids.thunder_button.disabled = True
        # 更新ボタン
        self.ids.file_screen.ids.refresh_button.disabled = True

        # バックグラウンド★サービス開始
        Clock.schedule_once(self.setup_android_and_start_service, 0)

    # ★★★androidセットアップ、サービス開始
    def setup_android_and_start_service(self, dt):
        # 1. 既に起動済みなら、何もしないで帰る
        if hasattr(self, 'service_started') and self.service_started:
            print("DEBUG: Service already started. Skipping setup.")
            Log.info('サービスは既に起動済みです。セットアップをスキップします。')
            return

        """Android環境でレシーバーを登録し、サービスを開始"""
        if platform == 'android':
            Log.info('Android環境でレシーバーを登録し、サービスを開始')
            # 2. 権限リクエスト
            request_permissions([
                Permission.INTERNET, 
                Permission.WAKE_LOCK, 
                Permission.FOREGROUND_SERVICE
            ])
            Log.info('権限リクエスト完了')

            # 3. レシーバーの作成と登録（受け皿を先に作る）
            # ※MyReceiverクラスの定義などはここにある想定
            self.br = BroadcastReceiver(
                self.on_broadcast_received, 
                actions=[ACTION_UPDATE]
            )
            Log.info('レシーバー作成完了')
            if hasattr(self.br, 'receiver'):
                intent_filter = IntentFilter()
                intent_filter.addAction(ACTION_UPDATE)
                # Android 14対応
                Log.info('レシーバー登録中... (Android 14対応)')
                currentActivity.registerReceiver(
                    self.br.receiver, 
                    intent_filter, 
                    ContextCompat.RECEIVER_NOT_EXPORTED
                )
            Log.info('レシーバー登録完了')

            # 4. 全ての準備が整ってからサービスを開始！
            self.start_service()
            Log.info('サービス開始完了')

            # 5. 最後に「起動済みフラグ」を立てる
            self.service_started = True
            print("DEBUG: Receiver registered and Service started.")
            Log.info('レシーバー登録とサービス開始完了')

    # ★★★サービス開始
    def start_service(self):  
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
            print("DEBUG: Started service with all required JNI extras.")

    def on_broadcast_received(self, context, intent):
        """ブロードキャストを受信した時のコールバック"""
        # intent からデータを取り出してUIを更新
        # android.broadcast が自動的にメインスレッドを考慮してくれるため
        # Clock.schedule_once を使わなくても安全な場合が多いです
        print("DEBUG: on_broadcast_received") # 追加
        Log.info('ブロードキャスト受信: {}'.format(intent.getAction()))
        # self.update_ui(context, intent)

    def on_stop(self):
        # アプリ終了時にレシーバーを停止（重要）
        if platform == 'android' and hasattr(self, 'br'):
            self.br.stop()
        super().on_stop()

    # バックグラウンドプロセス
    def background_process(self):
        Log.info('アップロード開始')

        self.process_file_no = 0

        # ローカルファイルを走査
        for filestat in self.file_store.files:
            # 処理中のファイル数
            self.process_file_no += 1
            # 処理中のファイル
            self.current_file = filestat

            # MAX_TRY_COUNTまで試行する
            #for i in range(1, DriveClient.MAX_TRY_COUNT + 1):
            for i in range(1, 999 + 1):
                # 状態：未→処理中（i回目）
                filestat.to_stat_progress(i)
                # 通知：処理中
                Clock.schedule_once(self.on_progress)
                try:
                    # アップロード実行
                    Log.info('{}：処理中({})...'.format(filestat.file_name, i))
                    # upload に渡すコールバックは filestat をキャプチャしたクロージャにする
                    # これにより、UI スレッドで実行されるときに current_file が変わっていても
                    # 正しい FileStat に対して進捗更新できる
                    self.client.upload(filestat, lambda pos, fs=filestat: self._upload_progress_from_thread(fs, pos))
                    Log.info('{}：完了({})'.format(filestat.file_name, i))
                    # # 状態：処理中→完了
                    filestat.to_stat_successful()
                    break
                except Exception as ex:
                    Log.error('{}：失敗({})\n{}'.format(filestat.file_name, i, repr(ex)))
                    # 最大試行回数
                    # if i == DriveClient.MAX_TRY_COUNT:
                    if i == 999:
                        # 状態：処理中→失敗
                        filestat.to_stat_failed()
                        # 通知：失敗
                        Clock.schedule_once(self.on_error)
                        return
                    else:
                        # リトライ時1秒ずつ遅延させる
                        time.sleep(i)

        # 通知：完了
        Clock.schedule_once(self.on_complete)

        Log.info('アップロード完了')

    # 処理中イベント処理
    def on_progress(self, dt):
        self.ids.file_screen.ids.msg.text = 'アップロード中... ({}/{})'.format(self.process_file_no, self.file_store.file_count)
        # ファイルアイテム更新
        self._refresh_file_item()

    # アップロード中イベント処理
    def on_upload_progress(self, filestat, range_pos):
        # filestat 固有で進捗を処理する（background_process の self.current_file に依存しない）
        Log.info('{}：{}MB アップ済'.format(filestat.file_name, '{:,.1f}'.format(FileStat.to_view_size(range_pos))))
        filestat.uploading(range_pos)
        from kivy.app import App
        app = App.get_running_app()
        # 値は 0-100 を使用しているのでそのまま割り当て（全体進捗を算出）
        app.progress_value = self.file_store.range_pos / self.file_store.file_size * 100
        # 色は処理中は黄とする
        app.progress_color = [1, 1, 0, 1]
        # ファイルアイテム更新（該当ファイルのみ）
        self._refresh_file_item(filestat)

    # 完了イベント処理
    def on_complete(self, dt):
        self.ids.file_screen.ids.msg.text = 'アップロード完了 ({}/{})'.format(self.process_file_no, self.file_store.file_count)
        # インジケーター：緑100
        from kivy.app import App
        app = App.get_running_app()
        app.progress_color = [0, 1, 0, 1]
        app.progress_value = 100
        # 更新ボタン活性化
        self.ids.file_screen.ids.refresh_button.disabled = False
        # ファイルアイテム更新
        self._refresh_file_item()

    # エラーイベント処理
    def on_error(self, dt):
        self.ids.file_screen.ids.msg.text = 'アップロード失敗'
        # インジケーター：赤
        from kivy.app import App
        app = App.get_running_app()
        app.progress_color = [1, 0, 0, 1]
        # 更新ボタン活性化
        self.ids.file_screen.ids.refresh_button.disabled = False
        # ファイルアイテム更新
        self._refresh_file_item()

    # ファイルアイテム更新
    def _refresh_file_item(self, filestat=None):
        # filestat が指定されればそのファイルのリストアイテムを更新する
        if filestat is None:
            idx = self.process_file_no - 1
            item = self.current_file
        else:
            try:
                idx = self.file_store.files.index(filestat)
            except ValueError:
                # filestat が見つからない場合は何もしない
                return
            item = filestat

        self.ids.file_screen.ids.rv.file_list[idx] = {}
        self.ids.file_screen.ids.rv.file_list[idx] = item.data

    # アップロード進捗通知のコールバック
    def _upload_progress_from_thread(self, filestat, range_pos):
        # UIスレッド上から実行する（filestat を渡す）
        Clock.schedule_once(lambda dt: self.on_upload_progress(filestat, range_pos), 0)

class ThunderloadApp(MDApp):
    # アプリ全体で共有する進捗プロパティ
    progress_value = NumericProperty(0)
    progress_color = ListProperty([1, 1, 0, 1])

    # コンストラクタ
    def __init__(self, **kwargs):
        super(ThunderloadApp, self).__init__(**kwargs)
        self.title = 'Thunderload'
        self.theme_cls.theme_style = 'Dark'
