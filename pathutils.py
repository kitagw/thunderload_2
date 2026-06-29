import os

from kivy.utils import platform


# アプリで使うベースディレクトリを取得する。
def get_base_path():
    # androidの場合は、ANDROID_PRIVATEをベースとする。
    if platform == 'android':
        base = os.environ.get('ANDROID_PRIVATE')
        if base and base.endswith('/app'):
            base = os.path.dirname(base)
        if base:
            ensure_dir(base)
            return base

    # androidでない場合は、resources配下をベースとする。
    repo_root = os.path.dirname(os.path.abspath(__file__))
    for candidate in (
        os.path.join(repo_root, 'resources'),
        os.path.join(os.getcwd(), 'resources'),
    ):
        if os.path.isdir(candidate):
            return candidate

    base = os.path.join(repo_root, 'resources')
    ensure_dir(base)
    return base

# ディレクトリを作成する。
def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path

# ベースパスを元に、指定した部分のファイルパスを取得する。
def get_resource_path(*parts):
    return os.path.join(ensure_dir(get_base_path()), *parts)
