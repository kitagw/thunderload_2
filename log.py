#-*- coding: utf-8 -*-
"""
ロガー
"""
class Log:
    func_print = None

    def handler(func):
        Log.func_print = func

    def info(log_text):
        if Log.func_print is not None:
            Log.func_print('INFO', '#00ffff', log_text)
        else:
            print(log_text)

    def warn(log_text):
        if Log.func_print is not None:
            Log.func_print('WARN', '#ffff00', log_text)
        else:
            print(log_text)

    def error(log_text):
        if Log.func_print is not None:
            Log.func_print('ERROR', '#ff0000', log_text)
        else:
            print(log_text)
