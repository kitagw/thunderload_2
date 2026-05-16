#-*- coding: utf-8 -*-

import datetime
import json
import threading
import traceback
import os
from action import Action
from config import Config
from log import Log
from driveclient import DriveClient
from filemanager import FileStat, LocalFileStore
from kivy.app import App
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
from progressmanager import ProgressManager

# Android APIのインポート（Linux上ではエラーになるため、try-exceptで囲む）
try:
    from jnius import autoclass # type: ignore
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

except ImportError:
    # Linux環境用のダミー
    class Dummy:
        def __getattr__(self, name): return self
    Intent, LocalBroadcastManager, PythonActivity, currentActivity, Service, IntentFilter = [Dummy()] * 6
    print("Running in desktop environment. Android APIs are mocked.")

# アプリ起動時に一度だけ呼ぶ
for p in [ProgressManager.get(ProgressManager.K_BACKLOG), ProgressManager.get(ProgressManager.K_PROCESSING), ProgressManager.get(ProgressManager.K_DONE)]:
    if not os.path.exists(p):
        os.makedirs(p, exist_ok=True)
        print(f"DEBUG: Created directory: {p}")

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
        Log.handler(self.add_log, '●')
        # DriveClient初期化
        try:
            # Log.info('DriveClient初期化中...')
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

    # 権限リクエストの結果コールバック
    def on_permissions_result(self, permissions, grant_results):
        # 通知、写真と動画の権限のリクエストコールバックで画面を初期化する（権限がないとファイルが読めないため）
        self.init_file_screen()

        if self.file_store.resume_upload:
            Log.info('前回の続きからアップロードを再開します')
            # サービス開始
            Clock.schedule_once(self.start_service, 0)
            
    # ファイルスクリーン初期化
    def init_file_screen(self):
        # ローカルファイルストア初期化
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
            Log.info('ローカルファイル読込完了')
        else:
            self.ids.file_screen.ids.msg.text = 'ファイルなし'
            Log.warn('ローカルファイルなし')

        # 稲妻ボタンは、ファイルが存在していてレジュームアップロードでない場合のみ活性化する
        if self.file_store.file_count > 0 and not self.file_store.resume_upload:
            self.ids.thunder_button.disabled = False

        # インジケーター更新：黄
        # 進捗値は self.file_storeで管理している処理済サイズから算出される（レジューム時には続きからの値となる）
        self._update_progress_indicator(color=[1, 1, 0, 1])

    # レシーバー登録
    def regist_broadcast_receiver(self):
        if platform == 'android':
            # レシーバーの作成と登録（受け皿を先に作る）
            # ※MyReceiverクラスの定義などはここにある想定
            self.br = BroadcastReceiver(
                self.on_broadcast_received, 
                actions=[Action.UPDATE, Action.LOG]
            )
            # Log.info('レシーバー作成完了')
            if hasattr(self.br, 'receiver'):
                intent_filter = IntentFilter()
                intent_filter.addAction(Action.UPDATE)
                intent_filter.addAction(Action.LOG)
                # Android 14対応
                # Log.info('レシーバー登録中...')
                currentActivity.registerReceiver(
                    self.br.receiver, 
                    intent_filter, 
                    ContextCompat.RECEIVER_NOT_EXPORTED
                )
            Log.info('レシーバー登録完了')

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
        # サービス開始
        Clock.schedule_once(self.start_service, 0)

    # サービス開始
    def start_service(self, dt):
        # 新規アップロードの場合は、進捗ファイルを初期化する（レジュームアップロードの場合は既存の進捗ファイルを使用する）
        if not self.file_store.resume_upload: 
            self.file_store.init_progress_files()
            Log.info('進捗ファイルを初期化しました')

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
            Log.info('サービス開始しました')

    def on_broadcast_received(self, context, intent):
        """ブロードキャストを受信した時のコールバック"""
        # intent からデータを取り出してUIを更新
        match intent.getAction():
            case Action.UPDATE:
                # intent から file_no と filestat と event を取り出す
                file_no_str = intent.getStringExtra('file_no')
                filestat_json = intent.getStringExtra('filestat')
                event_str = intent.getStringExtra('event')
                # これらが存在する場合のみ処理を行う（サービス側でイベント発生時に送信しているはずだが、念のため）
                if filestat_json and file_no_str and event_str:
                    try:
                        file_no = int(file_no_str)
                        filestat = FileStat(data=json.loads(filestat_json))
                        event = event_str

                        # file_no は 1-origin なので -1 してアクセス
                        idx = file_no - 1
                        self.file_store.files[idx].update_from(filestat) 
                        # ファイルアイテム更新
                        self._refresh_file_item(file_no, filestat)

                        # 進捗更新は、処理中のファイルに対してのみ行う（完了や失敗の更新は on_complete や on_error で行う）
                        match event:
                            case FileStat.E_FILE_PROGRESS:
                                Clock.schedule_once(lambda dt: self.on_file_progress(dt, file_no, filestat))
                            case FileStat.E_UPLOAD_PROGRESS:
                                Clock.schedule_once(lambda dt: self.on_upload_progress(dt, file_no, filestat))
                            case FileStat.E_COMPLETED:
                                # 最後のファイルの完了イベントを受け取ったら、完了処理を行う
                                if file_no == self.file_store.file_count:
                                    Clock.schedule_once(lambda dt: self.on_complete(dt, file_no, filestat))
                            case FileStat.E_ERROR:
                                Clock.schedule_once(lambda dt: self.on_error(dt, file_no, filestat))
                            case _:
                                Log.warning(f"Unknown event received: {event}") 

                    except Exception as e:
                        Log.error(traceback.format_exc())

            case Action.LOG:
                process_symbol_str = intent.getStringExtra('process_symbol')
                level_str = intent.getStringExtra('level')
                color_str = intent.getStringExtra('color')
                log_text_str = intent.getStringExtra('log_text')
                self.add_log(process_symbol_str, level_str, color_str, log_text_str)
            case _:
                Log.warning(f"Unknown action received: {intent.getAction()}")

    def on_stop(self):
        # アプリ終了時にレシーバーを停止（重要）
        if platform == 'android' and hasattr(self, 'br'):
            self.br.stop()
        super().on_stop()

    # 処理中イベント処理
    def on_file_progress(self, dt, file_no, filestat):
        self.ids.file_screen.ids.msg.text = 'アップロード中... ({}/{})'.format(file_no, self.file_store.file_count)

    # アップロード中イベント処理
    def on_upload_progress(self, dt, file_no, filestat):
        # インジケーター更新
        self._update_progress_indicator()

    # 完了イベント処理
    def on_complete(self, dt, file_no, filestat):
        self.ids.file_screen.ids.msg.text = 'アップロード完了 ({}/{})'.format(file_no, self.file_store.file_count)
        # インジケーター更新：緑100
        self._update_progress_indicator(value=100, color=[0, 1, 0, 1])
        # 更新ボタン活性化
        self.ids.file_screen.ids.refresh_button.disabled = False

    # エラーイベント処理
    def on_error(self, dt, file_no, filestat):
        self.ids.file_screen.ids.msg.text = 'アップロード失敗'
        # インジケーター更新：赤
        self._update_progress_indicator(color=[1, 0, 0, 1])
        # 更新ボタン活性化
        self.ids.file_screen.ids.refresh_button.disabled = False

    # ファイルアイテム更新
    def _refresh_file_item(self, file_no, filestat):
        # UI スレッド外から呼ばれた場合は UI スレッドで実行する
        if threading.current_thread() is not threading.main_thread():
            Clock.schedule_once(lambda dt: self._refresh_file_item(file_no, filestat), 0)
            return

        idx = file_no - 1
        self.ids.file_screen.ids.rv.file_list[idx] = {}
        self.ids.file_screen.ids.rv.file_list[idx] = filestat.data

    # インジケーター更新（UIスレッド上で実行する）
    def _update_progress_indicator(self, value=None, color=None):
        # UI スレッド外から呼ばれた場合は UI スレッドで実行する
        if threading.current_thread() is not threading.main_thread():
            Clock.schedule_once(lambda dt: self._update_progress_indicator(value, color), 0)
            return 

        app = App.get_running_app()
        # 値は 0-100 を使用しているのでそのまま割り当て（全体進捗を算出）
        if value is not None:
            app.progress_value = value
        else:
            app.progress_value = self.file_store.range_pos / self.file_store.file_size * 100
        # 色
        if color is not None:
            app.progress_color = color

class ThunderloadApp(MDApp):
    # アプリ全体で共有する進捗プロパティ
    progress_value = NumericProperty(0)
    progress_color = ListProperty([1, 1, 0, 1])

    # コンストラクタ
    def __init__(self, **kwargs):
        super(ThunderloadApp, self).__init__(**kwargs)
        self.title = 'Thunderload'
        self.theme_cls.theme_style = 'Dark'
