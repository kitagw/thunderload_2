'''
ロガー
'''
class Log:
    func_print = None
    process_name = None

    # 静的初期化
    @classmethod
    def set_handler(cls, func, process_name):
        cls.func_print = func
        cls.process_name = process_name

    # ログ出力
    @classmethod
    def info(cls, log_text):
        if cls.func_print is not None:
            cls.func_print(cls.process_name, 'INFO', '#00ffff', log_text)
        else:
            print(log_text)

    # 警告ログ出力
    @classmethod
    def warn(cls, log_text):
        if cls.func_print is not None:
            cls.func_print(cls.process_name, 'WARN', '#ffff00', log_text)
        else:
            print(log_text)

    # エラーログ出力
    @classmethod
    def error(cls, log_text):
        if cls.func_print is not None:
            cls.func_print(cls.process_name, 'ERROR', '#ff0000', log_text)
        else:
            print(log_text)
