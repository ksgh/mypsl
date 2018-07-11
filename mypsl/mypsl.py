#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK

'''
    mypsl :: MySQL process list watcher and query killer
    Copyright (C) 2014 Kyle Shenk <k.shenk@gmail.com>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

from __future__ import print_function
import os
import threading
import sys
import argparse
import time

from gen2.mysqldriver import mydb
from gen2.processlist import ProcessList
from gen2.processnode import ProcessNode
import gen2.connections as connections
import gen2.outputter as op

PROG_START = time.time()

try:
    import argcomplete
    HAS_ARGCOMPLETE = True
except ImportError:
    HAS_ARGCOMPLETE = False

INFO_TRIM_LENGTH        = 1000

'''
The following directory should contain files that should be in yaml format
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
    parser = argparse.ArgumentParser(description=op.cv('MySQL Process list watcher & query killer.', op.Fore.CYAN + op.Style.BRIGHT),
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
        print(op.cv("ERROR: Cannot kill using defaults!", op.Fore.RED + op.Style.BRIGHT))
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
    print('Quitting...')
    print()
    sys.exit(0)


def establish_node(args, sql, threaded=False):
    db_auth = connections.prep_db_connection_data(MYPSL_CONFIGS, args)
    db = mydb(db_auth)
    db.connect()

    if args.debug:
        if db.conn:
            print(op.cv(
                ' --> db connection ({0}) established'.format(db_auth['connect_type']),
                op.Fore.GREEN + op.Style.BRIGHT
            ))
        else:
            print(op.cv(
                ' --> db connection ({0}) failed'.format(db_auth['connect_type']),
                op.Fore.RED + op.Style.BRIGHT
            ))

    pn = ProcessNode(threading.Lock(), db, sql)
    if threaded == True:
        pn.start()

    return pn


def display_process_lists(pl, loop_interval):
    if loop_interval > 0:
        counter = 0
        while True:
            counter += 1
            if pl.process_row(counter):
                counter = 0

            time.sleep(loop_interval)
            pl.update(time.time())
    else:
        pl.process_row()


def main():
    args = parse_args()
    sql = compile_sql(args)

    processNode = establish_node(args, sql)
    pl = ProcessList(processNode, vars(args))

    try:
        display_process_lists(pl, args.loop_second_interval)
    except KeyboardInterrupt:
        __shutdown(processNode)

    try:
        processNode.join()
    except RuntimeError:
        pass


if __name__ == '__main__':
    main()
