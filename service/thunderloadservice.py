import json
import os
from action import Action
from driveclient import DriveClient
from filemanager import FileStat, LocalFileStore
from jnius import autoclass # type: ignore
from log import Log
from progressmanager import ProgressManager
from time import sleep

# Javaクラスのインポート
PythonService = autoclass('org.kivy.android.PythonService')
Context = autoclass('android.content.Context')
Intent = autoclass('android.content.Intent')
IntentFilter = autoclass('android.content.IntentFilter')
PendingIntent = autoclass('android.app.PendingIntent')
NotificationBuilder = autoclass('android.app.Notification$Builder')
NotificationChannel = autoclass('android.app.NotificationChannel')
NotificationManager = autoclass('android.app.NotificationManager')
PowerManager = autoclass('android.os.PowerManager')
String = autoclass('java.lang.String')

# 通知IDを定数にしておくと間違いがありません
NOTIFICATION_ID = 1

CHANNEL_ID = 'thunderload_service_channel'
CHANNEL_NAME = 'Thunderload Background Service'

# このクラスは、Androidのバックグラウンドサービスとして動作するための基本的な構造を提供します。
# サービスが開始されると、CPUを眠らせないようにWakeLockを取得し、フォアグラウンドサービスとして通知を表示します。
# サービスが停止されると、WakeLockを解放してCPUを眠らせるようにします。
# これにより、長時間のバックグラウンド処理が可能になりますが、ユーザーのバッテリー消費に注意が必要です。
# 実際のアップロード処理はrun_upload_loop()メソッド内で実装することができます。
class ThunderloadService():
    def __init__(self):
        self.service = PythonService.mService
        self.setup_foreground_service()
        self.acquire_wakelock()

    def setup_foreground_service(self):
        Log.info("setup_foreground_service - 1-1")
        # 1. 通知チャンネルの作成 (Android 8.0以上必須)
        importance = NotificationManager.IMPORTANCE_LOW
        channel = NotificationChannel(CHANNEL_ID, CHANNEL_NAME, importance)
        
        Log.info("setup_foreground_service - 1a-1")
        notification_manager = self.service.getSystemService(Context.NOTIFICATION_SERVICE)
        notification_manager.createNotificationChannel(channel)

        Log.info("setup_foreground_service - 2-1")
        # 2. 通知をタップしたときにアプリを開く設定
        app_context = self.service.getApplicationContext()
        app_intent = Intent(app_context, autoclass('org.kivy.android.PythonActivity'))
        app_intent.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_NEW_TASK)
        # アプリ起動時のメインアクションとして設定
        app_intent.setAction(Intent.ACTION_MAIN)
        app_intent.addCategory(Intent.CATEGORY_LAUNCHER)

        pending_intent = PendingIntent.getActivity(app_context, 0, app_intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE)

        Log.info("setup_foreground_service - 3-1")
        # 3. 通知の構築
        builder = NotificationBuilder(app_context, CHANNEL_ID)
        builder.setContentTitle("サービス実行中")
        builder.setContentText("バックグラウンドでデータを集計しています...")
        builder.setSmallIcon(self.service.getApplicationInfo().icon)
        builder.setContentIntent(pending_intent)
        notification = builder.build()

        Log.info("setup_foreground_service - 4-1")
        # 4. フォアグラウンドサービスとして開始
        # 第1引数は通知ID（0以外）、第2引数は通知オブジェクト
        self.service.startForeground(NOTIFICATION_ID, notification)

    def acquire_wakelock(self):
        # CPUを眠らせない設定
        power_manager = self.service.getSystemService(Context.POWER_SERVICE)
        wakelock = power_manager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "ThunderloadService:WakeLockTag")
        wakelock.acquire()
        self.wakelock = wakelock

    def release_wakelock(self):
        if self.wakelock and self.wakelock.isHeld():
            self.wakelock.release()
            self.wakelock = None
            Log.info("DEBUG: CPUを解放しました")

    def stop_service(self):
        # WakeLockを解除
        if self.wakelock:
            self._release_wakelock()
        
        # サービス自体を終了（これをしないと通知バーに残る）
        self.service.stopSelf()

    def run_upload(self):
        # アップロード進捗通知のコールバック
        def on_upload_progress(file_no, filestat, range_pos):
            Log.info('[{}] {}：{}MB アップ済'.format(file_no, filestat.file_name, '{:,.1f}'.format(FileStat.to_view_size(range_pos))))
            filestat.uploading(range_pos)
            self.send_filestat(file_no, filestat, FileStat.E_UPLOAD_PROGRESS)

        Log.info("ファイルのアップロードを開始します")

        # ローカルファイルストア初期化
        self.file_store = LocalFileStore()

        # DriveClient初期化
        try:
            Log.info('DriveClient初期化中...')
            self.client = DriveClient()
            Log.info('DriveClient初期化完了')
        except Exception as ex:
            Log.error('DriveClient初期化失敗\n' + repr(ex))
            return

        # ローカルファイルを走査
        file_no = 0
        for filestat in self.file_store.files:
            # 処理中のファイルNoを更新
            file_no += 1
            # ファイルの状態を確認して、未処理のファイルだけを処理する
            if filestat.status == FileStat.S_FINISHED:
                Log.info('[{}] {}：既済'.format(file_no, filestat.file_name))
                continue

            # MAX_TRY_COUNTまで試行する
            for i in range(1, DriveClient.MAX_TRY_COUNT + 1):
                # 状態：未→処理中（i回目）
                filestat.to_stat_progress(i)
                self.send_filestat(file_no, filestat, FileStat.E_FILE_PROGRESS)
                # 通知の内容を更新する
                self.update_notification(file_no, filestat)

                try:
                    # アップロード実行
                    Log.info('[{}] {}：処理中({})...'.format(file_no, filestat.file_name, i))
                    # upload に渡すコールバックは filestat をキャプチャしたクロージャにする
                    # これにより、UI スレッドで実行されるときに filestat が変わっていても
                    # 正しい FileStat に対して進捗更新できる
                    self.client.upload(filestat, lambda pos, fs=filestat: on_upload_progress(file_no, fs, pos))
                    Log.info('[{}] {}：完了({})'.format(file_no, filestat.file_name, i))
                    # 状態：処理中→完了
                    filestat.to_stat_successful()
                    self.send_filestat(file_no, filestat, FileStat.E_COMPLETED)
                    break
                except Exception as ex:
                    Log.error('[{}] {}：失敗({})\n{}'.format(file_no, filestat.file_name, i, repr(ex)))
                    # 最大試行回数
                    if i == DriveClient.MAX_TRY_COUNT:
                        # 状態：処理中→失敗
                        filestat.to_stat_failed()
                        # 通知：失敗
                        self.send_filestat(file_no, filestat, FileStat.E_ERROR)
                        return
                    else:
                        # リトライ時1秒ずつ遅延させる
                        sleep(i)

        # 進捗ファイル郡を削除する
        self.file_store.clear_progress_files()
        Log.info("全てのファイルの処理が完了しました")

    def send_filestat(self, file_no, filestat, event):
        """メインアプリへFileStatをブロードキャストする"""
        try:
            intent = Intent(Action.UPDATE)
            # 自分のアプリ内だけに送信することを明示（これが重要！）
            intent.setPackage(self.service.getPackageName())
            # FileStatオブジェクトをJSONに変換して送る
            intent.putExtra('file_no', String(str(file_no)))
            intent.putExtra('filestat', String(json.dumps(filestat.data)))
            intent.putExtra('event', String(str(event)))
            # ブロードキャストを送信
            self.service.sendBroadcast(intent)
        except Exception as e:
            Log.error(f"Exception: {e}")

    def send_log(self, process_name, level, color, log_text):
        """メインアプリへログをブロードキャストする"""
        try:
            intent = Intent(Action.LOG)
            # 自分のアプリ内だけに送信することを明示（これが重要！）
            intent.setPackage(self.service.getPackageName())
            intent.putExtra('process_name', String(str(process_name)))
            intent.putExtra('level', String(str(level)))
            intent.putExtra('color', String(str(color)))
            intent.putExtra('log_text', String(str(log_text)))
            # ブロードキャストを送信
            self.service.sendBroadcast(intent)
        except Exception as e:
            pass

    def update_notification(self, file_no, filestat):
        """通知の中身を更新する"""
        try:
            app_context = self.service.getApplicationContext()
            
            # 1. 再度インテントを作成（タップ時にアプリを開くため）
            app_intent = Intent(app_context, autoclass('org.kivy.android.PythonActivity'))
            app_intent.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_NEW_TASK)
            # アプリ起動時のメインアクションとして設定
            app_intent.setAction(Intent.ACTION_MAIN)
            app_intent.addCategory(Intent.CATEGORY_LAUNCHER)
            pending_intent = PendingIntent.getActivity(app_context, 0, app_intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE)

            # 2. Builderで新しい通知テキストを設定
            builder = NotificationBuilder(app_context, CHANNEL_ID)
            builder.setContentTitle(f"アップロード中... ({file_no}/{self.file_store.file_count})")
            # ファイル名を通知の内容に設定
            builder.setContentText(filestat.file_name) 
            builder.setSmallIcon(self.service.getApplicationInfo().icon)
            builder.setContentIntent(pending_intent)
            # 通知の音や振動を抑制する（更新のたびに鳴らないように）
            builder.setOnlyAlertOnce(True) 
            # 通知を構築        
            notification = builder.build()

            # 3. NotificationManagerを取得して更新を通知
            notification_manager = self.service.getSystemService(Context.NOTIFICATION_SERVICE)
            notification_manager.notify(NOTIFICATION_ID, notification)

        except Exception as e:
            Log.error(f"Notification update failed: {e}")
