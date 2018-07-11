from colorama import init, Fore, Style
import datetime

init()

def cv(val, color):
    return "%s%s%s" % (color, val, Style.RESET_ALL)

def get_now_date():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

