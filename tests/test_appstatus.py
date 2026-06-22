import os
import time
import tempfile

from appstatus import AppStatus


# テスト内容:
# - `AppStatus.set_status()` でステータスファイルが作成されること
# - `AppStatus.get_status()` / `AppStatus.is_status()` が期待どおりの値を返すこと
# - `AppStatus.get_last_status_update_time()` がフォーマット済みの文字列を返すこと
def test_appstatus_set_and_get(tmp_path):
    base = str(tmp_path)
    # テスト用のベースパスを差し替え
    AppStatus.BASE_PATH = base
    # ベースディレクトリを作成
    os.makedirs(base, exist_ok=True)

    # ステータスを `running` に設定して確認
    AppStatus.set_status(AppStatus.S_RUNNING)
    assert AppStatus.get_status() == AppStatus.S_RUNNING
    assert AppStatus.is_status(AppStatus.S_RUNNING)

    # 最終更新日時は空でないフォーマット済み文字列で返る
    t = AppStatus.get_last_status_update_time()
    assert isinstance(t, str) and len(t) > 0
