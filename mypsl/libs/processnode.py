
import time
import threading


class Node(threading.Thread):

    def __init__(self, db, collect_replication=False, defer_collection=False):
        super(Node, self).__init__()

        self.db = db
        self.collect_repl_info = collect_replication

        self.num_sleepers = 0
        self.hostname = None
        self.connected_threads = 0
        self.max_connections = 0
        self.long_query_time = 0
        self.slave_status = {}
        self.row = {}

        if defer_collection == False:
            self.update()


    def update(self):
        self.num_sleepers = self.__get_num_sleepers()
        self.hostname = self.__get_hostname()
        self.connected_threads = self.__get_connected_threads()
        self.max_connections = self.__get_max_connections()
        self.long_query_time = self.__get_long_query_time()

        if self.collect_repl_info:
            self.slave_status = self.__get_slave_status()

        return self


    def __get_num_sleepers(self):
        sql = """
            SELECT count(id) AS num_sleepers 
            FROM information_schema.processlist 
            WHERE (command = 'Sleep' OR state = 'User sleep')
            """
        cur = self.db.query(sql)
        res = cur.fetchone()
        if res and 'num_sleepers' in res:
            return int(res['num_sleepers'])
        return 0


    def __get_connected_threads(self):
        sql = "SHOW GLOBAL STATUS LIKE 'Threads_connected'"
        cur = self.db.query(sql)
        res = cur.fetchone()
        if res and 'Value' in res:
            return int(res['Value'])
        return 0


    def __get_slave_status(self):
        sql = "SHOW SLAVE STATUS"
        cur = self.db.query(sql)
        return cur.fetchone()


    def __get_max_connections(self):
        if self.max_connections:
            return self.max_connections

        sql = "SHOW GLOBAL VARIABLES LIKE 'max_connections'"
        cur = self.db.query(sql)
        res = cur.fetchone()
        if res and 'Value' in res:
            return int(res['Value'])
        return 0


    def __get_hostname(self):
        if self.hostname:
            return self.hostname

        ## we're going to ask the remote mysql server
        sql = "SELECT @@hostname AS hostname"
        cur = self.db.query(sql)
        res = cur.fetchone()
        if res and 'hostname' in res:
            return res['hostname']

        return None


    def __get_long_query_time(self):
        if self.long_query_time:
            return self.long_query_time

        sql = "SHOW GLOBAL VARIABLES LIKE 'long_query_time'"
        cur = self.db.query(sql)
        res = cur.fetchone()
        if res and 'Value' in res:
            return int(round(float(res['Value'])))

        return 0


class ProcessNode(Node):

    def __init__(self, thread_lock, db, sql, thread_sleep_time=2):
        super(ProcessNode, self).__init__(db)
        self.thread_lock = thread_lock
        self.sql = sql
        self.thread_sleep_time = thread_sleep_time
        self.blocking = False
        self.process_list = {}
        self.num_processes = 0


    def update(self):
        super(ProcessNode, self).update()
        self.process_list = self.__get_process_list()

        return self


    def run(self):
        self.thread_lock.acquire(self.blocking)
        while True:
            self.update()
            time.sleep(self.thread_sleep_time)


    def __get_process_list(self):
        try:
            cur = self.db.query(self.sql)
            res = cur.fetchall()

            self.num_processes = cur.rowcount
            return res
        except AttributeError:
            return None

