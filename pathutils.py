import os

from kivy.utils import platform


def get_app_base_path():
    """アプリで使うベースディレクトリを解決する。"""
    if platform == 'android':
        base = os.environ.get('ANDROID_PRIVATE')
        if base and base.endswith('/app'):
            base = os.path.dirname(base)
        if base:
            return base

    repo_root = os.path.dirname(os.path.abspath(__file__))
    for candidate in (
        os.path.join(repo_root, 'resources'),
        os.path.join(os.getcwd(), 'resources'),
    ):
        if os.path.isdir(candidate):
            return candidate

    return os.path.join(repo_root, 'resources')


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def get_resource_path(*parts):
    return os.path.join(ensure_dir(get_app_base_path()), *parts)
