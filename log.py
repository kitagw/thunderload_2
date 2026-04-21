#-*- coding: utf-8 -*-
"""
ロガー
"""
class Log:
    func_print = None
    process_name = None

    def handler(func, process_name):
        Log.func_print = func
        Log.process_name = process_name

    def info(log_text):
        if Log.func_print is not None:
            Log.func_print(Log.process_name, 'INFO', '#00ffff', log_text)
        else:
            print(log_text)

    def warn(log_text):
        if Log.func_print is not None:
            Log.func_print(Log.process_name, 'WARN', '#ffff00', log_text)
        else:
            print(log_text)

    def error(log_text):
        if Log.func_print is not None:
            Log.func_print(Log.process_name, 'ERROR', '#ff0000', log_text)
        else:
            print(log_text)
