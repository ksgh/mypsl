import os
import yaml
import exceptions as Gen2Exception


def __load_from_config(config_dir, args, connect_dict):
    cfile = os.path.join(config_dir, args.connect_config)
    if os.path.isfile(cfile):
        with open(cfile, 'r') as f:
            connect_dict.update(yaml.load(f))
            return connect_dict

    return {}

def __load_from_salt(args, pillar_key='mysql:connection'):
    connect_args= {}
    try:
        import salt.client
    except ImportError:
        raise Gen2Exception.SaltConfigError('Unable to import salt.client')

    lc = salt.client.LocalClient()

    data = lc.cmd(args.salt_minion, 'network.ip_addrs')

    if not data:
        raise Gen2Exception.SaltClientError('Error: Unable to get the IP address via network.ip_addrs')

    try:
        connect_args['host'] = data[args.salt_minion][0]
    except (KeyError, IndexError, TypeError):
        raise Gen2Exception.SaltClientError("Error: Unable to get the IP address.")

    data = lc.cmd(args.salt_minion, 'pillar.get', [pillar_key])

    if not data:
        raise Gen2Exception.SaltClientError("Error: Unable to get {0} from pillar.".format(pillar_key))

    try:
        connect_args['user']   = data[args.salt_minion]['user']
        connect_args['passwd'] = data[args.salt_minion]['pass']
    except KeyError:
        raise Gen2Exception.SaltClientError("Error: Unable to get 'user' or 'pass' from pillar data.")

    return connect_args


'''
    Ok so what we're doing here is this....
    First, setup a dict of whatever came from `args`, which were parsed via the CLI - some have defaults.
    Next, update that with anything from the config file - if one was specified and found - config file will override
    defaults.

    At this point nothing is stopping the user from specifying --salt-minion as well, which
'''
def prep_db_connection_data(config_dir, args):
    salt_connection = None

    db_connection = {
        'host': args.host,
        'passwd': args.passwd,
        'port': args.port,
        'user': args.user,
        'charset': args.charset,
        'salt_minion': args.salt_minion,
        'connect_type': 'default'
    }

    if args.connect_config:
        db_connection.update(__load_from_config(config_dir, args, db_connection))
        db_connection['connect_type'] = 'config'

    if args.salt_minion:
        salt_connection = __load_from_salt(args)

    if salt_connection:
        db_connection = salt_connection
        db_connection['connect_type'] = 'salt'

    return db_connection