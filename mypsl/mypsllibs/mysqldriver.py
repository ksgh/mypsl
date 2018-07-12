
from distutils.spawn import find_executable
import pymysql
import os
import subprocess

import outputter as op
import exceptions as Gen2Exception


def find_my_cnf():
    locations = (
        '/etc/my.cnf',
        '/etc/mysql/my.cnf',
        '/etc/mysql/conf.d/my.cnf',
        '/usr/etc/my.cnf',
    )

    for l in locations:
        if os.path.isfile(l):
            return l
    return None

def get_mysql_default(search_opt):
    my_print_defaults   = find_executable('my_print_defaults')
    my_cnf_file         = find_my_cnf()

    if not my_cnf_file:         return None
    if not my_print_defaults:   return None

    cmd     = [my_print_defaults, '--defaults-file', my_cnf_file, 'mysqld']
    proc    = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc.wait()

    if proc.returncode != 0:
        print(op.cv(proc.stderr.readlines(), op.Fore.RED + op.Style.BRIGHT))
        return None

    defaults = proc.stdout.readlines()

    if not defaults:
        return None

    for d in defaults:
        if d.startswith("--{0}".format(search_opt)):
            return d.split('=')[1].strip()
    return None

class mydb():
    conn            = None
    cursor          = None
    connect_args    = {}

    def __init__(self, margs, debug=False):

        self.connect_args = {
            'db':           'information_schema',
            'charset':      margs.get('charset', 'utf-8'),
            'cursorclass':  pymysql.cursors.DictCursor,
            'host':         margs.get('host', 'localhost'),
            'port':         margs.get('port', 3306),
            'user':         margs.get('user', ''),
            'passwd':       margs.get('passwd', '')
        }

        self.debug = debug

        if self.connect_args['host'] == 'localhost':
            socket = get_mysql_default('socket')
            if socket:
                self.connect_args['unix_socket'] = socket
                del self.connect_args['host']
                del self.connect_args['port']

        pymysql.paramstyle = 'pyformat'

    def connect(self):
        try:
            self.conn = pymysql.connect(**self.connect_args)
        except pymysql.Error as e:
            raise Gen2Exception.MyDBError("Unable to connect. MySQL Said: {0}: {1}".format(e.args[0],e.args[1]))


    def query(self, sql, args=[]):
        try:
            if not self.cursor:
                self.cursor = self.conn.cursor()

            if args:
                self.cursor.execute(sql, args)
            else:
                self.cursor.execute(sql)

        except (AttributeError, pymysql.OperationalError):
            self.connect()

            if self.debug == True:
                print('pymysql exception, retrying...')

            self.query(sql, args)

        if self.cursor:
            return self.cursor

        return False


    def close(self):
        self.cursor_close()
        self.db_close()


    def cursor_close(self):
        if self.cursor:
            self.cursor.close()

    def db_close(self):
        if self.conn:
            self.conn.close()