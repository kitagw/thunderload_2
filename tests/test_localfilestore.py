import json
import os

from fileinfo import FileInfo
from localfilestore import LocalFileStore
from progressmanager import ProgressManager


# テスト内容:
# - `filelist.json` を読み込み、`LocalFileStore` が `files` を初期化できること
# - ファイルカウントや合計サイズが期待どおりになること
def test_localfilestore_reads_filelist(tmp_path):
    base = tmp_path / 'progress'
    backlog = base / 'backlog'
    processing = base / 'processing'
    done = base / 'done'
    backlog.mkdir(parents=True)
    processing.mkdir()
    done.mkdir()

    # ProgressManager のパスをテスト用に差し替え
    ProgressManager.items = {
        ProgressManager.K_PROGRESS_BASE: str(base),
        ProgressManager.K_BACKLOG: str(backlog),
        ProgressManager.K_PROCESSING: str(processing),
        ProgressManager.K_DONE: str(done),
    }

    # 実ファイルを作成して filelist.json を用意する
    f1_path = tmp_path / 'one.jpg'
    f2_path = tmp_path / 'two.jpg'
    f1_path.write_bytes(b'123')
    f2_path.write_bytes(b'abcd')

    data = [
        {FileInfo.K_FILE_PATH: str(f1_path), FileInfo.K_FILE_NAME: 'one.jpg', FileInfo.K_FILE_SIZE: 3},
        {FileInfo.K_FILE_PATH: str(f2_path), FileInfo.K_FILE_NAME: 'two.jpg', FileInfo.K_FILE_SIZE: 4},
    ]
    with open(os.path.join(str(base), 'filelist.json'), 'w') as f:
        json.dump(data, f, ensure_ascii=False)

    # LocalFileStore は filelist.json を読み込み、files を初期化する
    store = LocalFileStore()
    assert store.file_count == 2
    assert store.file_size == 7
