from action import Action
from jnius import autoclass # type: ignore
from time import sleep

# Javaクラスのインポート
Log = autoclass('android.util.Log')
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

TAG = 'SERVICE_DEBUG'
# カスタムアクション名
# ACTION_UPDATE = 'org.kitagw.thunderload_2.UPLOAD_PROGRESS_UPDATE'
# ACTION_LOG = 'org.kitagw.thunderload_2.LOG'

# 通知IDを定数にしておくと間違いがありません
NOTIFICATION_ID = 1

CHANNEL_ID = 'thunderload_service_channel'
CHANNEL_NAME = 'Thunderload Background Service'


#このクラスは、Androidのバックグラウンドサービスとして動作するための基本的な構造を提供します。サービスが開始されると、CPUを眠らせないようにWakeLockを取得し、フォアグラウンドサービスとして通知を表示します。サービスが停止されると、WakeLockを解放してCPUを眠らせるようにします。これにより、長時間のバックグラウンド処理が可能になりますが、ユーザーのバッテリー消費に注意が必要です。実際のアップロード処理はrun_upload_loop()メソッド内で実装することができます。
class ThunderloadService():
    def __init__(self):
        self.service = PythonService.mService
        self.wakelock = None

    # def on_start(self):
    #     try:
    #         # 2. アップロードのメインループ実行
    #         self.run_upload_loop()
    #     finally:
    #         # 3. 何があっても（エラーが起きても）最後はCPUを解放する
    #         self.stop_service()

    # def stop_service(self):
    #     # WakeLockを解除
    #     if self.wakelock:
    #         self.release_wakelock()
        
    #     # サービス自体を終了（これをしないと通知バーに残る）
    #     # PythonService.mService.stopSelf() など
    #     self.service.stopSelf()

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
            print("DEBUG: CPUを解放しました。おやすみなさい。")

    def setup_foreground_service(self):
        Log.i(TAG, "setup_foreground_service - 1-1")
        # 1. 通知チャンネルの作成 (Android 8.0以上必須)
        importance = NotificationManager.IMPORTANCE_LOW
        channel = NotificationChannel(CHANNEL_ID, CHANNEL_NAME, importance)
        
        Log.i(TAG, "setup_foreground_service - 1a-1")
        notification_manager = self.service.getSystemService(Context.NOTIFICATION_SERVICE)
        notification_manager.createNotificationChannel(channel)

        Log.i(TAG, "setup_foreground_service - 2-1")
        # 2. 通知をタップしたときにアプリを開く設定
        app_context = self.service.getApplicationContext()
        app_intent = Intent(app_context, autoclass('org.kivy.android.PythonActivity'))
        app_intent.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_NEW_TASK)
        # アプリ起動時のメインアクションとして設定
        app_intent.setAction(Intent.ACTION_MAIN)
        app_intent.addCategory(Intent.CATEGORY_LAUNCHER)

        pending_intent = PendingIntent.getActivity(app_context, 0, app_intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE)

        Log.i(TAG, "setup_foreground_service - 3-1")
        # 3. 通知の構築
        builder = NotificationBuilder(app_context, CHANNEL_ID)
        builder.setContentTitle("サービス実行中")
        builder.setContentText("バックグラウンドでデータを集計しています...")
        builder.setSmallIcon(self.service.getApplicationInfo().icon)
        builder.setContentIntent(pending_intent)
        notification = builder.build()

        Log.i(TAG, "setup_foreground_service - 4-1")
        # 4. フォアグラウンドサービスとして開始
        # 第1引数は通知ID（0以外）、第2引数は通知オブジェクト
        self.service.startForeground(NOTIFICATION_ID, notification)

    def send_broadcast(self, start_time, counter):
        """メインアプリへデータをブロードキャストする"""
        try:
            intent = Intent(Action.UPDATE)
            # 自分のアプリ内だけに送信することを明示（これが重要！）
            intent.setPackage(self.service.getPackageName())
            intent.putExtra('start_time', String(str(start_time)))
            intent.putExtra('counter', String(str(counter)))

            # ログ確認用
            Log.i(TAG, f"START Sent start_time={start_time}, counter={counter}")
            # サービス自身のsendBroadcastメソッドを使用
            self.service.sendBroadcast(intent)
            # ログ確認用
            Log.i(TAG, f"END Sent start_time={start_time}, counter={counter}")
        except Exception as e:
            Log.i(TAG, f"Exception: {e}")

    def log(self, log_text):
        try:
            intent = Intent(Action.LOG)
            # 自分のアプリ内だけに送信することを明示（これが重要！）
            intent.setPackage(self.service.getPackageName())
            intent.putExtra('log_text', String(str(log_text)))

            # ログ確認用
            self.service.sendBroadcast(intent)
        except Exception as e:
            Log.i(TAG, f"Exception: {e}")

    def update_notification(self, counter):
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
            builder.setContentTitle("サービス稼働中")
            # ここでカウンターを表示
            builder.setContentText(f"現在のカウント: {counter} 秒経過") 
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
            Log.e(TAG, f"Notification update failed: {e}")
