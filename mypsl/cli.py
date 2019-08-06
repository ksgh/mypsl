#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK

'''
    mypsl :: MySQL process list watcher and query killer
    MIT License

    Copyright (c) 2018 Kyle Shenk

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
'''

from __future__ import print_function
import os
import threading
import sys
import argparse
import time

from libs.mysqldriver import mydb
from libs.processlist import ProcessList
from libs.processnode import ProcessNode
import libs.connections as connections
import libs.outputter as op

PROG_START = time.time()

try:
    import argcomplete
    HAS_ARGCOMPLETE = True
except ImportError:
    HAS_ARGCOMPLETE = False

INFO_TRIM_LENGTH        = 1000

'''
The following directory should contain files that are in yaml format
host: stuff.example.com
user: kshenk
passwd: things
port: 3306
'''
MYPSL_CONFIGS   = os.path.join(os.environ.get('HOME'), '.mypsl')

def _get_config_files(prefix, parsed_args, **kwargs):
    if not HAS_ARGCOMPLETE:
        return False
    if not os.path.isdir(MYPSL_CONFIGS):
        return False
    return next(os.walk(MYPSL_CONFIGS))[2]


def parse_args():
    parser = argparse.ArgumentParser(description=op.cv('(mypsl: {0}) :: MySQL Process list watcher & query killer.'.format(get_version()), op.Fore.CYAN + op.Style.BRIGHT),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    con_opt_group   = parser.add_argument_group(op.cv('Connection Options', op.Fore.YELLOW + op.Style.BRIGHT))
    config_group    = parser.add_argument_group(op.cv('Configuration Options', op.Fore.YELLOW + op.Style.BRIGHT))
    kill_group      = parser.add_argument_group(op.cv('Kill Options', op.Fore.RED + op.Style.BRIGHT))

    con_opt_group.add_argument('-H', '--host', dest='host', type=str, default='localhost',
        help='The host to get the process list from. If localhost, we will attempt to find and use the socket file first.')
    con_opt_group.add_argument('-p', '--port', dest='port', type=int, default=3306,
        help="The host's port. If the host is localhost, we will attempt to find and use the socket file first.")
    con_opt_group.add_argument('-u', '--user', dest='user', type=str, default='root',
        help='The user to connect to the host as.')
    con_opt_group.add_argument('-P', '--pass', dest='passwd', type=str, default='',
        help='The password for authentication.')
    #con_opt_group.add_argument('-S', '--socket', dest='socket', type=str,
    #    help='If connecting locally, optionally use this socket file instead of host/port.')
    con_opt_group.add_argument('-ch', '--charset', dest='charset', type=str, default='utf8',
        help='Charset to use with the database.')
    con_opt_group.add_argument('--config', dest='connect_config', type=str, default=None,
        help='Load connection configuration from a file in {0}. Just provide the filename. '.format(MYPSL_CONFIGS) + \
        'This will override any other connection information provided').completer = _get_config_files
    con_opt_group.add_argument('-sm', '--salt-minion', dest='salt_minion', type=str, default=None,
        help='Connect to mysql running on a salt minion. Do not use any other connection options with this. \
        mysql:connection:user and mysql:connection:pass must exist in pillar data.')

    ## ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    config_group.add_argument('-l', '--loop', dest='loop_second_interval', type=int, default=0,
        help='Time in seconds between getting the process list.')
    config_group.add_argument('-lm', '--loop_max', dest='loop_max', type=int, default=None,
        help='If specified we will stop execution when the loop interval reaches this number')
    config_group.add_argument('-dft', '--default', dest='default', action='store_true',
        help='Run with defaults. Loop interval: 3 seconds, command like query or connect, order by time asc, id asc, truncate query to {0}.'.format(INFO_TRIM_LENGTH))
    config_group.add_argument('-c', '--command', dest='command', type=str,
        help='Lookup processes running as this command.')
    config_group.add_argument('-s', '--state', dest='state', type=str,
        help='Lookup processes running in this state.')
    config_group.add_argument('-t', '--time', dest='time', type=int,
        help='Lookup processes running longer than the specified time in seconds.')
    config_group.add_argument('-d', '--database', dest='database', type=str,
        help='Lookup processes running against this database.')
    config_group.add_argument('-q', '--query', dest='query', type=str,
        help='Lookup processes where the query starts with this specification.')
    config_group.add_argument('-i', '--id', dest='id_only', action='store_true',
        help='Only print back the ID of the processes.')
    config_group.add_argument('-isr', '--ignore_system_user', dest='ignore_system_user', action='store_true',
        help="Ignore the 'system user'")
    config_group.add_argument('--debug', dest='debug', action='store_true',
        help='Provide debug output.')
    config_group.add_argument('-o', '--order_by', dest='order_by', type=str,
        help='Order the results by a particular column: "user", "db asc", "db desc", "time desc"...etc')
    config_group.add_argument('-T', '--trim_info', dest='trim_info', action='store_true',
        help='Trim the info field (the query) to {0}'.format(INFO_TRIM_LENGTH))
    config_group.add_argument('-v', '--version', dest='version', action='store_true',
                              help='Show the installed program version and quit.')
    config_group.add_argument('--send-notification', dest='send_notification', action='store_true',
        help='Send a notification to slack anytime we kill a query. Slack Auth/Config file must exist @ ~/.slack_auth')

    ## ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    kill_group.add_argument('--kill', dest='kill', action='store_true',
        help='Kill the queries that we find.')
    kill_group.add_argument('-kt', '--kill_threshold', dest='kill_threshold', default=100,
        help="The kill threshold. If a number is provided, we'll need to hit that many total connections before killing queries. You can \
        set this to 'off' as well, which kills queries no matter how many connections there are.")
    kill_group.add_argument('-ka', '--kill_all', dest='kill_all', action='store_true',
        help="If this flag is provided, we'll attempt to kill everything, not only select queries. {0}".format(op.cv("Use with caution!", op.Fore.RED + op.Style.BRIGHT)))
    kill_group.add_argument('-ky', '--kill_yes', dest='kill_yes', action='store_true',
        help="If this is provided we won't stop to ask if you are sure that you want to kill queries.")
    kill_group.add_argument('-kl', '--kill_log', dest='kill_log', default='/var/log/killed_queries.log',
        help="Where to log killed queries to, granting permissions to write to this file.")
    kill_group.add_argument('-klo', '--kill_log_only', dest='kill_log_only', action='store_true',
        help="Only log the queries that would be killed, do not actually kill them")

    if HAS_ARGCOMPLETE:
        argcomplete.autocomplete(parser)
    return parser.parse_args()

def compile_sql(args):
    where = []
    order_by = []
    where_str = ''
    order_by_str = ''
    select_fields = ['id']

    if args.id_only and args.kill:
        print(op.cv("ERROR: Cannot specify id only (-i, --id) with kill!", op.Fore.RED + op.Style.BRIGHT))
        sys.exit(1)

    if args.kill and args.default:
        print(op.cv("ERROR: whoooaaaa no no no. You cannot kill using defaults!", op.Fore.RED + op.Style.BRIGHT))
        sys.exit(1)

    if args.kill:
        if not args.kill_yes:
            ans = raw_input(op.cv("Are you sure you want to kill queries? ", op.Style.BRIGHT))
            if ans.lower() not in ('y', 'yes'):
                print("Ok, then only use --kill when you are sure you want to kill stuff.")
                sys.exit(0)

    if not args.id_only:
        select_fields.extend(['user', 'host', 'db', 'command', 'time', 'state', 'info'])

    sql = "SELECT {0} FROM processlist".format(', '.join(select_fields))

    if args.default:
        where.append("(command = 'Query' OR command = 'Connect')")
        where.append("(command != 'Sleep')")
        args.loop_second_interval = 3
        args.ignore_system_user = True
        args.trim_info = True
        order_by = ['time ASC', 'id ASC']
    else:
        if args.command:
            where.append("command = '{0}'".format(args.command))
        if args.state:
            where.append("state = '{0}'".format(args.state))
        if args.time:
            where.append("time >= {0}".format(args.time))
        if args.database:
            where.append("db = '{0}'".format(args.database))
        if args.query:
            where.append("info LIKE '{0}%'".format(args.query))
        if args.order_by:
            order_by.append(args.order_by)

    if args.kill and not where:
        print(op.cv("ERROR: Cannot kill without specifying criteria!", op.Fore.RED + op.Style.BRIGHT))
        sys.exit(1)

    where.append("command != 'Binlog Dump'")
    where.append("(db != 'information_schema' OR db IS NULL)")  ## confuses me why I had to add OR db IS NULL

    if args.ignore_system_user == True:
        where.append("user != 'system user'")

    if where:
        where_str = 'WHERE {0}'.format(' AND '.join(where))

    if order_by:
        order_by_str = 'ORDER BY {0}'.format(', '.join(order_by))

    sql = ' '.join([sql, where_str, order_by_str])

    if args.debug:
        op.show_processing_time(PROG_START, time.time(), 'Program Preparation')
        print("SQL: {0}".format(op.cv(sql, op.Fore.CYAN)))

    return sql


def __shutdown(node_thread):
    try:
        node_thread.join()
    except RuntimeError:
        pass
    if node_thread.db:
        db = node_thread.db
        try:
            db.cursor_close()
            db.db_close()
        except Exception as e:
            print(op.cv(str(e), op.Fore.RED + op.Style.BRIGHT))

    print(op.cv('Quitting...', op.Fore.CYAN + op.Style.BRIGHT))
    print()
    sys.exit(0)


def establish_node(args, sql, threaded=False):
    db_auth = connections.prep_db_connection_data(MYPSL_CONFIGS, args)
    db = mydb(db_auth)
    db.connect()

    if args.debug:
        if db.conn:
            print(op.cv(
                ' --> db connection ({0}) established'.format(db_auth['host']),
                op.Fore.GREEN + op.Style.BRIGHT
            ))
        else:
            print(op.cv(
                ' --> db connection ({0}) failed'.format(db_auth['host']),
                op.Fore.RED + op.Style.BRIGHT
            ))

    pn = ProcessNode(threading.Lock(), db, sql)
    if threaded == True:
        pn.start()

    return pn


def __loop_control(counter, max):
    if max is None or isinstance(max, str):
        return True

    if max > 0:
        if counter < max:
            return True
        else:
            return False
    else:
        print(op.cv('The max loop interval should be greater than 0...'))
        sys.exit(1)


def display_process_lists(pl, loop_interval, loop_max):
    if loop_interval > 0:
        counter = 0
        while __loop_control(counter, loop_max):
            counter += 1
            if pl.process_processes(counter):
                counter = 0

            time.sleep(loop_interval)
            pl.update(time.time())
    else:
        pl.process_row()


def get_version():
    from libs._version import __version__
    return 'mypsl: {}'.format(__version__)


def main():
    args = parse_args()

    if args.version:
        print(get_version())
        sys.exit(0)

    sql = compile_sql(args)

    processNode = establish_node(args, sql).update()
    pl = ProcessList(processNode, vars(args))

    try:
        display_process_lists(pl, args.loop_second_interval, args.loop_max)
    except KeyboardInterrupt:
        __shutdown(processNode)

    try:
        processNode.join()
    except RuntimeError:
        pass

    sys.exit(0)


if __name__ == '__main__':
    main()
