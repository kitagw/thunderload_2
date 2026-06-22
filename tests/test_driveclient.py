import importlib
import json
import sys
import types


def setup_fake_sys_modules():
    # テスト用説明:
    # - `driveclient.py` がインポートする外部ライブラリ（msal, office365 等）を
    #   簡易なダミーモジュールに差し替えることで、実際の外部通信を行わずに
    #   ロジックの単体テストを行えるようにする。
    # - 既にダミーをセットしている場合は再生成しない（例外クラスの同一性を保つため）。
    # driveclient.py が import する外部ライブラリをテスト用の簡易モジュールで差し替える。
    # 例外クラスの identity を保つため、すでに作成済みなら再生成しない。
    if 'msal' in sys.modules:
        return

    # msal
    msal = types.ModuleType('msal')
    class PublicClientApplication:
        def __init__(self, client_id=None, authority=None):
            self.client_id = client_id
            self.authority = authority
        def acquire_token_interactive(self, scopes):
            return {"access_token":"at_inter","refresh_token":"rt_inter"}
        def acquire_token_by_refresh_token(self, refresh_token, scopes):
            return {"access_token":"at_ref","refresh_token":"rt_ref"}
    msal.PublicClientApplication = PublicClientApplication
    sys.modules['msal'] = msal

    # office365.graph_client
    og = types.ModuleType('office365.graph_client')
    class GraphClient:
        def __init__(self, token_func):
            self.token_func = token_func
            # minimal structure used by upload path navigation
            self.me = types.SimpleNamespace(drive=types.SimpleNamespace(root=types.SimpleNamespace()))
    og.GraphClient = GraphClient
    sys.modules['office365.graph_client'] = og

    # office365.onedrive.driveitems.driveItem
    od = types.ModuleType('office365.onedrive.driveitems.driveItem')
    class ConflictBehavior:
        Fail = 'Fail'
    class DriveItem: pass
    od.ConflictBehavior = ConflictBehavior
    od.DriveItem = DriveItem
    sys.modules['office365.onedrive.driveitems.driveItem'] = od

    # office365.runtime.client_request_exception
    cre = types.ModuleType('office365.runtime.client_request_exception')
    class ClientRequestException(Exception):
        def __init__(self, code):
            self.code = code
    cre.ClientRequestException = ClientRequestException
    sys.modules['office365.runtime.client_request_exception'] = cre


def test_init_with_existing_tokens(tmp_path, monkeypatch):
    # テスト内容:
    # - 既存の `tokens.json` が存在する場合に、`DriveClient` がそれを読み込んで
    #   内部 `tokens` を初期化できることを確認する。
    # - モックされた `msal`/`office365` を利用して、実際の認証フローを実行せず
    #   `GraphClient` が生成されることを検証する。
    # 既存の tokens.json がある場合は、それを読み込んで GraphClient を初期化できることを確認する。
    setup_fake_sys_modules()
    driveclient = importlib.import_module('driveclient')
    tok = tmp_path / 'tokens.json'
    tok.write_text(json.dumps({"refresh_token":"rt_existing","access_token":"at_existing"}))

    monkeypatch.setattr(driveclient.DriveClient, 'TOKENS_JSON_PATH', str(tok))

    def fake_get(key):
        if key == driveclient.Config.K_CLIENT_ID:
            return 'cid'
        if key == driveclient.Config.K_AUTHORITY:
            return 'auth'
        if key == driveclient.Config.K_UPLOAD_PATH:
            return 'upath'
        return None
    monkeypatch.setattr(driveclient.Config, 'get', staticmethod(fake_get))

    dc = driveclient.DriveClient()
    assert dc.client is not None
    assert dc.tokens['refresh_token'] == 'rt_existing'


def test_init_without_tokens_creates_file(tmp_path, monkeypatch):
    # テスト内容:
    # - `tokens.json` が存在しない場合に `DriveClient` の初期化が対話認証を模した
    #   ダミーの結果を保存し、新しい `tokens.json` を作成することを確認する。
    # tokens.json が存在しない場合は、対話認証の結果を保存して新規作成することを確認する。
    setup_fake_sys_modules()
    importlib.invalidate_caches()
    driveclient = importlib.import_module('driveclient')
    tok = tmp_path / 'tokens2.json'
    monkeypatch.setattr(driveclient.DriveClient, 'TOKENS_JSON_PATH', str(tok))
    monkeypatch.setattr(driveclient.Config, 'get', staticmethod(lambda k: 'v'))

    if tok.exists():
        tok.unlink()
    dc = driveclient.DriveClient()
    assert tok.exists()
    data = json.loads(tok.read_text())
    assert 'refresh_token' in data


def test_acquire_token_by_refresh_token_writes_file(tmp_path, monkeypatch):
    # テスト内容:
    # - 内部で `acquire_token_by_refresh_token` を呼ぶ処理が新しいトークンを受け取り、
    #   その結果が `tokens` とファイルに書き戻されることを検証する。
    # refresh_token を使った更新処理が新しいトークンを返し、ファイルにも書き戻すことを確認する。
    setup_fake_sys_modules()
    driveclient = importlib.import_module('driveclient')
    tok = tmp_path / 'tokens3.json'
    monkeypatch.setattr(driveclient.DriveClient, 'TOKENS_JSON_PATH', str(tok))
    monkeypatch.setattr(driveclient.Config, 'get', staticmethod(lambda k: 'v'))

    dc = driveclient.DriveClient()
    # ensure dc.tokens exists for refresh
    dc.tokens = {'refresh_token': 'rt_old'}
    res = dc._DriveClient__acquire_token_by_refresh_token()
    assert 'refresh_token' in res
    assert tok.exists()


def test_create_folder_ignores_nameAlreadyExists(monkeypatch):
    # テスト内容:
    # - OneDrive 側で同名フォルダ作成時に `nameAlreadyExists` の例外が発生しても、
    #   `DriveClient` のフォルダ作成処理がこれを捕捉して無視し、例外を外に出さないことを確認する。
    # 既に同名フォルダがある場合は、OneDrive 側の nameAlreadyExists 例外を握りつぶして継続する。
    setup_fake_sys_modules()
    driveclient = importlib.import_module('driveclient')
    monkeypatch.setattr(driveclient.Config, 'get', staticmethod(lambda k: 'v'))
    dc = driveclient.DriveClient()

    class Dummy:
        def create_folder(self, name, cb):
            class E:
                def execute_query(self):
                    from office365.runtime.client_request_exception import (
                        ClientRequestException,
                    )
                    raise ClientRequestException('nameAlreadyExists')
            return E()
        @property
        def resource_path(self):
            return '/rp'

    # should not raise
    dc._DriveClient__create_folder(Dummy(), 'folder')
