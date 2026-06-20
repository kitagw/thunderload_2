import os

from kivy.core.text import DEFAULT_FONT, LabelBase
from kivy.resources import resource_add_path

from thunderload import ThunderloadApp

# デフォルトフォント指定
default_font_path = os.path.join(os.path.dirname(__file__), 'fonts', 'NotoSansJP-Regular.ttf')
resource_add_path(os.path.dirname(default_font_path))
LabelBase.register(DEFAULT_FONT, default_font_path)

# ログフォント指定
log_font_path = os.path.join(os.path.dirname(__file__), 'fonts', 'PlemolJPHS-Regular.ttf')
resource_add_path(os.path.dirname(log_font_path))
LabelBase.register('log_font', log_font_path)

# アプリケーション起動
if __name__ == '__main__':
    ThunderloadApp().run()
