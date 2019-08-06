
from collections import defaultdict
from .notification import Notification
from .exceptions import NotificationError
import os
import time
import outputter as op

READ_SEARCH     = ('show', 'select', 'desc')
WRITE_SEARCH    = ('insert', 'update', 'create', 'alter', 'replace', 'rename', 'delete')
LOCKED_SEARCH   = ('locked', 'waiting for table level lock', 'waiting for table metadata lock')

PROCESS_THRESHOLD_WARN  = 100
PROCESS_THRESHOLD_CRIT  = 200
SLEEPER_THRESHOLD_WARN  = 30
SLEEPER_THRESHOLD_CRIT  = 75
INFO_TRIM_LENGTH        = 1000

class ProcessList():

    def __init__(self, process_node, config):
        self.process_node = process_node
        self.start_time = time.time()
        self.config = config

    def update(self, start_time):
        self.start_time = start_time
        self.process_node = self.process_node.update()

        return self

    def print_header(self):
        ct = self.process_node.connected_threads
        mc = self.process_node.max_connections

        if (ct > (mc * .75)):
            ct_str = op.cv(ct, op.Fore.RED)
        elif (ct > (mc * .5)):
            ct_str = op.cv(ct, op.Fore.YELLOW)
        else:
            ct_str = op.cv(ct, op.Fore.CYAN)

        bar = "-" * 35
        header = "%s%s%s %s%s :: %s :: Threads (%s / %s) %s%s%s" % \
            (op.Fore.YELLOW, bar, op.Fore.GREEN, self.process_node.hostname, op.Fore.RESET, op.get_now_date(), ct_str, mc, op.Fore.YELLOW, bar, op.Fore.RESET)

        print(header)
        print("{0}".format(op.Style.BRIGHT) +
              op.OUT_FORMAT.format("ID", "USER", "HOST", "DB", "COMMAND", "TIME", "STATE", "INFO") +
              "{0}".format(op.Style.RESET_ALL))

    def process_row(self):
        num_reads = num_writes = num_locked = num_closing = num_opening = num_past_long_query = 0

        user_count          = defaultdict(int)
        state_count         = defaultdict(int)

        for row in self.process_node.process_list:
            if self.config.get('id_only'):
                print(row['id'])
                continue

            user_count[row['user']]     += 1
            state_count[row['state']]   += 1

            if row['info']:
                ## pull the first word of the query out - newline, tab or whitespace, and lowercase it.
                s_info = row['info'].split()[0].lower()
                if self.config.get('trim_info') and len(row['info']) > 1000:
                    row['info'] = "%s ..." % row['info'][:1000]
            else:
                row['info'] = '--'
                s_info = '--'

            if not row['state']:    row['state'] = '--'
            if not row['db']:       row['db'] = '--'

            ## the port number doesn't really tell us much.
            row['host'] = row['host'].split(':')[0]

            if s_info:
                if s_info in READ_SEARCH:   num_reads += 1
                if s_info in WRITE_SEARCH:  num_writes += 1

            if row['state']:
                if row['state'].lower() in LOCKED_SEARCH:           num_locked += 1
                if row['state'] == 'Copying to tmp table on disk':  num_writes += 1
                if row['state'].startswith('Opening table'):        num_opening += 1
                if row['state'].startswith('closing table'):        num_closing += 1

            if int(row['time']) > self.process_node.long_query_time: num_past_long_query += 1

            print \
                (op.OUT_FORMAT.format(row['id'], row['user'], row['host'], row['db'], row['command'], row['time'], row['state'], row['info'].encode('utf-8')))

        if self.config.get('id_only'):
            return

        return {
            'num_reads':            num_reads,
            'num_writes':           num_writes,
            'num_locked':           num_locked,
            'num_closing':          num_closing,
            'num_opening':          num_opening,
            'num_past_long_query':  num_past_long_query,
            'user_count':           user_count,
            'state_count':          state_count
        }


    def process_processes(self, counter=0):

        if not self.process_node.process_list:
            ## just sending a message to the terminal to let the user that the script is still working, and isn't stuck.
            if counter % 4 == 0:
                print(op.cv("{0} :: ({1}) :: Still looking...".format(op.get_now_date(), self.process_node.hostname), op.Style.BRIGHT))
            return False

        if self.config.get('kill'):
            kills = self.murdah()
            if kills:
                print(op.cv(op.get_now_date() + " :: " + self.process_node.hostname +
                        " :: Killed: " + str(kills) + " (SQL CRITERIA: {0})".format(self.process_node.sql), op.Fore.RED + op.Style.BRIGHT))
            return

        if not self.config.get('id_only'):
            self.print_header()

        _nums = self.process_row()

        if self.config.get('id_only'):
            ## then we're done here.
            return True

        num_reads           = _nums['num_reads']
        num_writes          = _nums['num_writes']
        num_locked          = _nums['num_locked']
        num_closing         = _nums['num_closing']
        num_opening         = _nums['num_opening']
        num_past_long_query = _nums['num_past_long_query']
        user_count          = _nums['user_count']
        state_count         = _nums['state_count']

        ## format total processes
        if self.process_node.num_processes >= PROCESS_THRESHOLD_CRIT:
            num_processes = op.cv(self.process_node.num_processes, op.Fore.RED)
        elif self.process_node.num_processes >= PROCESS_THRESHOLD_WARN:
            num_processes = op.cv(self.process_node.num_processes, op.Fore.YELLOW)
        else:
            num_processes = op.cv(self.process_node.num_processes, op.Fore.CYAN)

        ## format the number of queries past the long query time
        if num_past_long_query > 0:
            num_past_long_query = op.cv(num_past_long_query, op.Fore.RED)
        else:
            num_past_long_query = op.cv(num_past_long_query, op.Fore.CYAN)

        ## format the number of sleepers
        if self.process_node.num_sleepers >= SLEEPER_THRESHOLD_CRIT:
            num_sleepers = op.cv(self.process_node.num_sleepers, op.Fore.RED)
        elif self.process_node.num_sleepers >= SLEEPER_THRESHOLD_WARN:
            num_sleepers = op.cv(self.process_node.num_sleepers, op.Fore.YELLOW)
        else:
            num_sleepers = op.cv(self.process_node.num_sleepers, op.Fore.CYAN)

        print \
            ("\n\t({0}) PROCESSES: {1}, SLEEPERS: {2}, LOCKED: {3}, READS: {4}, WRITES: {5}, CLOSING: {6}, OPENING: {7}, PAST LQT: {8}"
              .format(op.cv(self.process_node.hostname, op.Fore.GREEN), num_processes, num_sleepers, op.cv(num_locked, op.Fore.CYAN),
                      op.cv(num_reads, op.Fore.CYAN), op.cv(num_writes, op.Fore.CYAN), op.cv(num_closing, op.Fore.CYAN),
                      op.cv(num_opening, op.Fore.CYAN), num_past_long_query))

        ## this is ok, but the next one sorts by occurrence
        # mystr = "{0}".format( ', '.join("%s: %s" % (k, "{0}".format(color_val(v, Fore.CYAN))) for (k, v) in user_count.iteritems()) )
        user_str = "{0}".format( ', '.join("%s: %s" % (k, "{0}".format(op.cv(user_count[k], op.Fore.CYAN))) \
                                           for k in sorted(user_count, key=user_count.get, reverse=True)) )
        state_str = "{0}".format(', '.join("%s: %s" % (k, "{0}".format(op.cv(state_count[k], op.Fore.CYAN))) \
                                           for k in sorted(state_count, key=state_count.get, reverse=True)))

        print("\t({0}) {1}".format(op.cv("Users", op.Fore.GREEN), user_str))
        print("\t({0}) {1}".format(op.cv("States", op.Fore.GREEN), state_str))

        print(op.show_processing_time(self.start_time, time.time()))

        print('')

        return True


    def record_kill(self, row):

        if self.config.get('send_notification'):
            proxies = {
                'http': 'http://proxy.svcs:3128',
                'https': 'http://proxy.svcs:3128'
            }
            msg = 'Query Killed on {hostname}'.format(hostname=self.process_node.hostname)

            # No need to bail if we just can't send the slack notification
            try:
                # Notification configuration is handled in the service definition
                notifier = Notification(proxies)
                # When sending an email notification, currently the 3rd argument (icon) doesn't have any affect
                notifier.send(msg, row, {'icon': ':jason:'})
            except Exception as e:
                # Anything that may have happened in there doesn't have to stop the show
                print(e)

        if os.path.exists(self.config.get('kill_log')):
            if not os.access(self.config.get('kill_log'), os.W_OK):
                return
        try:
            with open(self.config['kill_log'], 'a') as f:
                kill_string = "{0} :: {1} :: {2}\n".format(op.get_now_date(), self.process_node.hostname,
                                                           ', '.join(
                                                               "%s: %s" % (k, v) for (k, v) in row.items()))
                f.write(kill_string)

        except IOError:
            print(op.cv("Unable to write to: {0}".format(self.config['kill_log']), op.Fore.RED + op.Style.BRIGHT))
            return


    def murdah(self):
        ## ok. is it an integer and are the connected threads greater than the kill threshold ?
        try:
            kill_threshold = int(self.config.get('kill_threshold'))
            if self.process_node.connected_threads < kill_threshold:
                print("Connected threads: {0}, Kill threshold: {1}. Not killing at this time".format(
                    self.process_node.connected_threads, kill_threshold)
                )
                return
        except ValueError:
            if self.config.get('kill_threshold').lower() != 'off':
                ## if we haven't set this to off, then no killing
                print("kill threshold was set but doesn't = off. Not killing at this time.")
                return

        sql = "KILL %s"
        killed = 0
        for row in self.process_node.process_list:
            if not self.config.get('kill_all'):
                if not row['info'].lower().startswith('select'):
                    continue

            if self.config.get('kill_log_only'):
                self.record_kill(row)
            elif self.process_node.db.query(sql, (row['id'],)):
                self.record_kill(row)
                killed += 1

        return killed
