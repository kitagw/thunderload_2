import json
import os
import tempfile

from fileinfo import FileInfo
from progressmanager import ProgressManager


def make_fileinfo(name, size=10):
    # テスト用の簡易 FileInfo を辞書で生成して返す
    return FileInfo(data={
        FileInfo.K_FILE_NAME: name,
        FileInfo.K_FILE_PATH: f'/tmp/{name}',
        FileInfo.K_FILE_SIZE: size,
        FileInfo.K_STATUS: FileInfo.S_UNPROCESSED,
        FileInfo.K_RANGE_POS: 0,
    })


# テスト内容:
# - backlog/processing/done フォルダ間のファイル移動（遷移）が正しく行われること
# - `init_progress()` が `filelist.json` を作成すること
# - `clear_progress()` が進捗情報を削除すること
def test_progress_lifecycle(tmp_path):
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

    f1 = make_fileinfo('file1.jpg')

    # backlog にファイルを作成してから load_progress を呼び、状態を確認
    open(os.path.join(str(backlog), f1.file_name), 'w').close()
    ProgressManager.load_progress([f1])
    assert f1.status == FileInfo.S_UNPROCESSED

    # backlog -> processing に移動できること
    ProgressManager.transition_backlog_to_processing(f1)
    assert not os.path.exists(os.path.join(str(backlog), f1.file_name))
    assert os.path.exists(os.path.join(str(processing), f1.file_name))

    # processing -> done に移動できること
    ProgressManager.transition_processing_to_done(f1)
    assert not os.path.exists(os.path.join(str(processing), f1.file_name))
    assert os.path.exists(os.path.join(str(done), f1.file_name))

    # init_progress が filelist.json を作成すること
    f2 = make_fileinfo('a.jpg')
    f3 = make_fileinfo('b.jpg')
    ProgressManager.init_progress([f2, f3])
    fl = os.path.join(str(base), 'filelist.json')
    assert os.path.exists(fl)
    with open(fl, 'r') as f:
        data = json.load(f)
    assert isinstance(data, list) and len(data) == 2

    # clear_progress が filelist.json を削除すること
    ProgressManager.clear_progress()
    assert not os.path.exists(fl)
