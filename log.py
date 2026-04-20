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
            Log.func_print('INFO', '#00ffff', Log.process_name, log_text)
        else:
            print(log_text)

    def warn(log_text):
        if Log.func_print is not None:
            Log.func_print('WARN', '#ffff00', Log.process_name, log_text)
        else:
            print(log_text)

    def error(log_text):
        if Log.func_print is not None:
            Log.func_print('ERROR', '#ff0000', Log.process_name, log_text)
        else:
            print(log_text)
