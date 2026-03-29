import os
from kivy.utils import platform

class ProgressManager():
    K_PROGRESS_BASE = 'PROGRESS_BASE'
    K_BACKLOG = 'BACKLOG'
    K_PROCESSING = 'PROCESSING'
    K_DONE = 'DONE'

    items = {}

    @classmethod
    def _initialize_static(cls):
        # ベースとなるパスの決定
        if platform == 'android':
            BASE = os.environ['ANDROID_PRIVATE']
        else:
            BASE = os.path.abspath('./resources')

        # 各ステータス用フォルダのパス
        ProgressManager.items[ProgressManager.K_PROGRESS_BASE] = os.path.join(BASE, 'progress')
        ProgressManager.items[ProgressManager.K_BACKLOG] = os.path.join(ProgressManager.items[ProgressManager.K_PROGRESS_BASE], 'backlog')
        ProgressManager.items[ProgressManager.K_PROCESSING] = os.path.join(ProgressManager.items[ProgressManager.K_PROGRESS_BASE], 'processing')
        ProgressManager.items[ProgressManager.K_DONE] = os.path.join(ProgressManager.items[ProgressManager.K_PROGRESS_BASE], 'done')

        # アプリ起動時に一度だけ呼ぶ
        for p in ProgressManager.items.values():
            if not os.path.exists(p):
                os.makedirs(p, exist_ok=True)
                print(f"DEBUG: Created directory: {p}")

    # 取得
    def get(key):
        return ProgressManager.items[key] if key in ProgressManager.items else ''

ProgressManager._initialize_static()
