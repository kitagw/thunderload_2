import json
from time import sleep

from jnius import autoclass  # type: ignore

from action import Action
from appstatus import AppStatus
from driveclient import DriveClient
from localfilestore import FileInfo, LocalFileStore
from log import Log
from progressmanager import ProgressManager

# AndroidのクラスをJavaのパッケージ名で指定して取得
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

# 通知ID（0以外の整数を指定）
NOTIFICATION_ID = 1

# 通知チャンネルIDと名前
CHANNEL_ID = 'thunderload_service_channel'
CHANNEL_NAME = 'Thunderload Background Service'

'''
ThunderloadServiceは、バックグラウンドで動作するサービスのクラスです。
このサービスは、ローカルファイルをOneDriveにアップロードする処理を実行し、その進捗や状態をメインアプリにブロードキャストで通知します。
サービスは、Androidのフォアグラウンドサービスとして実装されており、CPUを眠らせないようにWakeLockを使用しています。
サービスは、以下の機能を提供します：
- フォアグラウンドサービスの設定と通知の表示
- CPUを眠らせないためのWakeLockの取得と解放
- アップロード処理の実行と進捗の通知
- メインアプリへのAppStatusの更新通知
- メインアプリへのFileInfoの更新通知
- メインアプリへのログの通知
サービスは、アップロード処理の開始前に実行状態を確認し、停止中の場合は処理を開始せず、停止済に状態を変更します。
アップロード処理中は、各ファイルの状態を更新しながら、進捗をメインアプリに通知します。
処理が完了したファイルは完了状態に更新され、全てのファイルの処理が完了したらAppStatusを完了に更新します。
処理中に停止要求があった場合は、停止状態に更新して処理を中断します。
処理中にエラーが発生した場合は、失敗状態に更新して処理を中断します。
'''
class ThunderloadService():
    # サービスの初期化
    def __init__(self):
        self.service = PythonService.mService
        self.setup_foreground_service()
        self.acquire_wakelock()

    # フォアグラウンドサービスの設定
    def setup_foreground_service(self):
        # 1. 通知チャンネルの作成 (Android 8.0以上必須)
        importance = NotificationManager.IMPORTANCE_LOW
        channel = NotificationChannel(CHANNEL_ID, CHANNEL_NAME, importance)
        
        notification_manager = self.service.getSystemService(Context.NOTIFICATION_SERVICE)
        notification_manager.createNotificationChannel(channel)

        # 2. 通知をタップしたときにアプリを開く設定
        app_context = self.service.getApplicationContext()
        app_intent = Intent(app_context, autoclass('org.kivy.android.PythonActivity'))
        app_intent.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_NEW_TASK)
        # アプリ起動時のメインアクションとして設定
        app_intent.setAction(Intent.ACTION_MAIN)
        app_intent.addCategory(Intent.CATEGORY_LAUNCHER)

        pending_intent = PendingIntent.getActivity(app_context, 0, app_intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE)

        # 3. 通知の構築
        builder = NotificationBuilder(app_context, CHANNEL_ID)
        builder.setContentTitle("サービス実行中")
        builder.setContentText("バックグラウンドでデータを集計しています...")
        builder.setSmallIcon(self.service.getApplicationInfo().icon)
        builder.setContentIntent(pending_intent)
        notification = builder.build()

        # 4. フォアグラウンドサービスとして開始
        # 第1引数は通知ID（0以外）、第2引数は通知オブジェクト
        self.service.startForeground(NOTIFICATION_ID, notification)

    # CPUを眠らせないWakeLockの取得
    def acquire_wakelock(self):
        # CPUを眠らせない設定
        power_manager = self.service.getSystemService(Context.POWER_SERVICE)
        wakelock = power_manager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "ThunderloadService:WakeLockTag")
        wakelock.acquire()
        self.wakelock = wakelock

    # CPUを眠らせないWakeLockの解放
    def release_wakelock(self):
        if self.wakelock and self.wakelock.isHeld():
            self.wakelock.release()
            self.wakelock = None
            Log.info("DEBUG: CPUを解放しました")

    # サービスの停止
    def stop_service(self):
        # WakeLockを解除
        if self.wakelock:
            self._release_wakelock()
        
        # サービス自体を終了（これをしないと通知バーに残る）
        self.service.stopSelf()

    # アップロード処理の実行
    def run_upload(self):
        # アップロード進捗通知のコールバック
        def on_upload_progress(file_no, fileinfo, range_pos):
            Log.info('[{}] {}：{}MB アップ済'.format(file_no, fileinfo.file_name, '{:,.1f}'.format(FileInfo.to_view_size(range_pos))))
            fileinfo.uploading(range_pos)
            self.send_fileinfo(file_no, fileinfo, FileInfo.E_UPLOAD_PROGRESS)

        # アップロード開始前に、実行中かどうかを確認する
        if not AppStatus.is_status(AppStatus.S_RUNNING):
            Log.info(f"アップロードは開始しませんでした（実行状態が「実行中({AppStatus.S_RUNNING})」ではないため）")
            # 停止中の場合は、停止済に変更する
            if AppStatus.is_status(AppStatus.S_STOPPING):
                Log.info(f"実行状態が「停止中({AppStatus.S_STOPPING})」のため「停止済({AppStatus.S_STOPPED})」に変更します")
                AppStatus.set_status(AppStatus.S_STOPPED)

            return

        Log.info("アップロードを開始します")

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
        for fileinfo in self.file_store.files:
            # 処理中のファイルNoを更新
            file_no += 1
            # ファイルの状態を確認して、未処理のファイルだけを処理する
            if fileinfo.status == FileInfo.S_FINISHED:
                Log.info('[{}] {}：既済'.format(file_no, fileinfo.file_name))
                continue

            # MAX_TRY_COUNTまで試行する
            for i in range(1, DriveClient.MAX_TRY_COUNT + 1):
                # 停止中の場合は、停止する
                if AppStatus.is_status(AppStatus.S_STOPPING):
                    AppStatus.set_status(AppStatus.S_STOPPED)

                    Log.info("アップロードを停止しました")
                    return

                # 状態：未→処理中（i回目）
                fileinfo.to_stat_progress(i)
                # 最初の試行のときに、進捗ファイルをbacklogからprocessingに移動する
                if i == 1:
                    ProgressManager.transition_backlog_to_processing(fileinfo)
                # 通知：処理中
                self.send_fileinfo(file_no, fileinfo, FileInfo.E_FILE_PROGRESS)
                # 通知の内容を更新する
                self.update_notification(file_no, fileinfo)

                try:
                    # アップロード実行
                    Log.info('[{}] {}：処理中({})...'.format(file_no, fileinfo.file_name, i))
                    # upload に渡すコールバックは FileInfo をキャプチャしたクロージャにする
                    # これにより、UI スレッドで実行されるときに fileinfo が変わっていても
                    # 正しい FileInfo に対して進捗更新できる
                    self.client.upload(fileinfo, lambda pos, fs=fileinfo: on_upload_progress(file_no, fs, pos))
                    Log.info('[{}] {}：完了({})'.format(file_no, fileinfo.file_name, i))
                    # 状態：処理中→完了
                    fileinfo.to_stat_successful()
                    # 進捗ファイルをprocessingからdoneに移動する
                    ProgressManager.transition_processing_to_done(fileinfo)
                    # 通知：完了
                    self.send_fileinfo(file_no, fileinfo, FileInfo.E_COMPLETED)
                    break
                except Exception as ex:
                    Log.error('[{}] {}：失敗({})\n{}'.format(file_no, fileinfo.file_name, i, repr(ex)))
                    # 最大試行回数
                    if i == DriveClient.MAX_TRY_COUNT:
                        # 状態：処理中→失敗
                        fileinfo.to_stat_failed()
                        # 通知：失敗
                        self.send_fileinfo(file_no, fileinfo, FileInfo.E_ERROR)
                        # AppStatus：失敗
                        AppStatus.set_status(AppStatus.S_ERROR)
                        return
                    else:
                        # リトライ時1秒ずつ遅延させる
                        sleep(i)

        # AppStatus：完了
        AppStatus.set_status(AppStatus.S_COMPLETE)
        Log.info("全てのファイルの処理が完了しました")

    # メインアプリへAppStatusの更新をブロードキャストする
    def send_appstatus(self):
        try:
            intent = Intent(Action.APP)
            # 自分のアプリ内だけに送信することを明示（これが重要！）
            intent.setPackage(self.service.getPackageName())
            # ブロードキャストを送信
            self.service.sendBroadcast(intent)
        except Exception as e:
            Log.error(f"Exception: {e}")

    # メインアプリへFileInfoの更新をブロードキャストする
    def send_fileinfo(self, file_no, fileinfo, event):
        try:
            intent = Intent(Action.UPDATE)
            # 自分のアプリ内だけに送信することを明示（これが重要！）
            intent.setPackage(self.service.getPackageName())
            # FileInfoオブジェクトをJSONに変換して送る
            intent.putExtra('file_no', String(str(file_no)))
            intent.putExtra('fileinfo', String(json.dumps(fileinfo.data)))
            intent.putExtra('event', String(str(event)))
            # ブロードキャストを送信
            self.service.sendBroadcast(intent)
        except Exception as e:
            Log.error(f"Exception: {e}")

    # メインアプリへログをブロードキャストする
    def send_log(self, process_symbol, level, color, log_text):
        try:
            intent = Intent(Action.LOG)
            # 自分のアプリ内だけに送信することを明示（これが重要！）
            intent.setPackage(self.service.getPackageName())
            intent.putExtra('process_symbol', String(str(process_symbol)))
            intent.putExtra('level', String(str(level)))
            intent.putExtra('color', String(str(color)))
            intent.putExtra('log_text', String(str(log_text)))
            # ブロードキャストを送信
            self.service.sendBroadcast(intent)
        except Exception as e:
            pass

    # 通知の内容を更新する
    def update_notification(self, file_no, fileinfo):
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
            builder.setContentText(fileinfo.file_name) 
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
