import json
import os
import tempfile

import config


# テスト内容:
# - `Config.set()` で設定を保存できること
# - `Config.get()` で保存した値が読み出せること
# - 保存先の JSON ファイルが正しく書き込まれること
def test_config_set_get(tmp_path):
    cfg = config.Config
    # 設定のバックアップ（テスト後に復元するため）
    orig_path = cfg.JSON_PATH
    orig_items = dict(cfg.items) if cfg.items is not None else None

    try:
        # 一時ファイルを設定ファイルとして使う
        tmpfile = tmp_path / 'config.json'
        cfg.JSON_PATH = str(tmpfile)
        cfg.items = {}

        # 値を設定して取得できるか確認
        cfg.set('key1', 'value1')
        assert cfg.get('key1') == 'value1'

        # ファイルに正しく書き込まれていることを確認
        with open(cfg.JSON_PATH, 'r') as f:
            data = json.load(f)
        assert data['key1'] == 'value1'
    finally:
        # 元の設定を復元
        cfg.JSON_PATH = orig_path
        cfg.items = orig_items
