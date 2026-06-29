import os

import pathutils


def test_ensure_dir_creates_directory(tmp_path):
    # ensure_dir() は指定したパスのディレクトリを再帰的に作成し、
    # 作成後も同じ文字列パスを返すことを確認する。
    target = tmp_path / "nested" / "dir"
    assert not target.exists()

    returned = pathutils.ensure_dir(str(target))

    assert returned == str(target)
    assert target.is_dir()


def test_get_resource_path_joins_parts(tmp_path, monkeypatch):
    # get_resource_path() は get_base_path() の結果をベースにして、
    # 可変個引数を os.path.join で結合したパスを返す。
    monkeypatch.setattr(pathutils, "get_base_path", lambda: str(tmp_path))

    resource_path = pathutils.get_resource_path("subdir", "file.txt")

    assert resource_path == os.path.join(str(tmp_path), "subdir", "file.txt")
    assert os.path.isdir(str(tmp_path))


def test_get_base_path_android_uses_android_private_parent(tmp_path, monkeypatch):
    # Android 環境時、ANDROID_PRIVATE 環境変数が /app で終わる場合に
    # その親ディレクトリをベースパスとして返すことを確認する。
    monkeypatch.setattr(pathutils, "platform", "android")
    app_dir = tmp_path / "ANDROID_PRIVATE" / "app"
    app_dir.mkdir(parents=True)
    monkeypatch.setenv("ANDROID_PRIVATE", str(app_dir))

    base_path = pathutils.get_base_path()

    assert base_path == str(app_dir.parent)
    assert os.path.isdir(base_path)


def test_get_base_path_uses_cwd_resources_when_repo_resources_missing(tmp_path, monkeypatch):
    # リポジトリ側 resources が存在しない場合、cwd の resources を優先する。
    # この際、cwd の resources が存在すればそのパスを返すことを確認する。
    repo_root = os.path.dirname(os.path.abspath(pathutils.__file__))
    repo_resource = os.path.join(repo_root, "resources")
    cwd_resource = os.path.join(str(tmp_path), "resources")
    (tmp_path / "resources").mkdir()

    original_isdir = pathutils.os.path.isdir

    def fake_isdir(path):
        if path == repo_resource:
            return False
        if path == cwd_resource:
            return True
        return original_isdir(path)

    monkeypatch.setattr(pathutils.os.path, "isdir", fake_isdir)
    monkeypatch.setattr(pathutils.os, "getcwd", lambda: str(tmp_path))

    base_path = pathutils.get_base_path()

    assert base_path == cwd_resource
    assert os.path.isdir(base_path)


def test_get_base_path_creates_repo_resources_when_none_exist(monkeypatch):
    # どちらの resources も存在しない場合、リポジトリ配下 resources を作成し、
    # そのパスを返すことを確認する。
    repo_root = os.path.dirname(os.path.abspath(pathutils.__file__))
    repo_resource = os.path.join(repo_root, "resources")

    original_isdir = pathutils.os.path.isdir
    original_makedirs = pathutils.os.makedirs

    def fake_isdir(path):
        if path == os.path.join(repo_root, "resources"):
            return False
        if path == os.path.join(os.getcwd(), "resources"):
            return False
        return original_isdir(path)

    def fake_makedirs(path, exist_ok=False):
        pathutils.os.path.isdir = original_isdir
        try:
            return original_makedirs(path, exist_ok=exist_ok)
        finally:
            pathutils.os.path.isdir = fake_isdir

    monkeypatch.setattr(pathutils.os.path, "isdir", fake_isdir)
    monkeypatch.setattr(pathutils.os, "makedirs", fake_makedirs)

    base_path = pathutils.get_base_path()

    assert base_path == repo_resource
    assert original_isdir(base_path)
