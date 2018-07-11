from colorama import init, Fore, Style
import datetime

init()

OUT_FORMAT      = "{0:<12}{1:16}{2:20}{3:22}{4:25}{5:<8}{6:28}{7:25}"

def cv(val, color):
    return "%s%s%s" % (color, val, Style.RESET_ALL)

def get_now_date():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def show_processing_time(start, end, text='Processing time'):
    elapsed = round(end - start, 3)

    if elapsed > 5:
        elapsed_str = cv(elapsed, Fore.RED)
    elif elapsed > .5:
        elapsed_str = cv(elapsed, Fore.YELLOW)
    else:
        elapsed_str = cv(elapsed, Fore.CYAN)

    return "\t({0}): {1}".format(cv(text, Fore.GREEN), elapsed_str)
