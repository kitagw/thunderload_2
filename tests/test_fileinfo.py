from fileinfo import FileInfo

# モジュール全体のテスト説明:
# - `FileInfo.to_view_size()` の表示用サイズ変換ロジックを確認する。
# - `FileInfo` の状態遷移（未処理→処理中→完了→失敗）や進捗更新、
#   他インスタンスからのデータ上書き (`update_from`) が正しく動作することを検証する。


def test_to_view_size_zero():
    # 0 バイトはそのまま 0 表示になることを確認する。
    assert FileInfo.to_view_size(0) == 0


def test_to_view_size_small():
    # 0.1MB 未満は、UI 表示用に最小値の 0.1 MB に丸める。
    size = int(FileInfo.MBYTE_SIZE * 0.05)
    assert FileInfo.to_view_size(size) == 0.1


def test_to_view_size_large():
    # 1MB を超えるサイズは、そのまま MB 単位の実数値で返す。
    assert FileInfo.to_view_size(FileInfo.MBYTE_SIZE * 2) == 2


def test_status_transitions_and_update():
    # テストシナリオ詳細:
    # 1) インスタンス `a` を未処理状態で初期化
    # 2) `to_stat_progress()` を呼んで処理中状態と試行回数が反映されることを確認
    # 3) `uploading()` で range_pos が更新されることを確認
    # 4) `to_stat_successful()` と `to_stat_failed()` による状態遷移を確認
    # 5) 別インスタンス `other` から `update_from()` でデータ上書きが行われることを確認
    base_data = {
        FileInfo.K_FILE_PATH: 'p',
        FileInfo.K_FILE_NAME: 'n',
        FileInfo.K_FILE_SIZE: 100,
        FileInfo.K_YEAR: '2020',
        FileInfo.K_DATE: '20200101_',
        FileInfo.K_STATUS: FileInfo.S_UNPROCESSED,
        FileInfo.K_TRY_COUNT: 0,
        FileInfo.K_RANGE_POS: 0,
    }
    a = FileInfo(data=dict(base_data))

    # to_stat_progress
    a.to_stat_progress(3)
    assert a.status == FileInfo.S_PROCESSING
    assert a.try_count == 3
    assert a.range_pos == 0

    # uploading
    a.uploading(512)
    assert a.range_pos == 512

    # to_stat_successful / failed
    a.to_stat_successful()
    assert a.status == FileInfo.S_FINISHED
    a.to_stat_failed()
    assert a.status == FileInfo.S_FAILED

    # update_from
    other = FileInfo(data={
        FileInfo.K_STATUS: FileInfo.S_PROCESSING,
        FileInfo.K_TRY_COUNT: 1,
        FileInfo.K_RANGE_POS: 123,
    })
    a.update_from(other)
    assert a.status == FileInfo.S_PROCESSING
    assert a.try_count == 1
    assert a.range_pos == 123
