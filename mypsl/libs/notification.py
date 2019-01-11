
import os
import ConfigParser
from datetime import datetime
from slackclient import SlackClient
from .exceptions import NotificationError

import pprint

pp = pprint.PrettyPrinter(indent=4)

'''
NOTE: There can be more than one slack channel. They must be separated by a comma.
----------------------------------------
`~/.slack_auth`
[slack]
username: jazzcibot
token: theSuperSecretToken
channels: #tech-jazzbot-noise,#second-optional-channelname
'''

class Notification():

    def __init__(self, query_data, proxies = None):

        self.query_data = query_data
        self.slack_auth_file = os.path.join(os.path.expanduser('~'), '.slack_auth')

        if not os.path.exists(self.slack_auth_file):
            raise NotificationError('Slack auth/config file not found! {f}'.format(f=self.slack_auth_file))

        self.proxies = proxies
        self.slack_config = None

        self.slack_client = self.__get_client()

    def __get_client(self):
        config = ConfigParser.ConfigParser()
        config.read(self.slack_auth_file)

        self.slack_config = {
            'username': config.get('slack', 'username'),
            'token': config.get('slack', 'token'),
            'channels': config.get('slack', 'channels').split(',')
        }

        return SlackClient(self.slack_config.get('token'), proxies=self.proxies)


    def send(self, msg='', icon=':mysql2:'):
        channels    = self.slack_config.get('channels')
        fields      = []

        for key, val in self.query_data.items():
            fields.append({
                'title': key,
                'value': val,
                'short': False if key == 'info' else True
            })

        attachments = [{
            'color':    '#E42217',
            'title':    msg,
            'fallback': msg,
            'fields':   fields,
            'footer':   'mypsl query killah',
            'ts':       datetime.now().timestamp()
        }]

        for channel in channels:
            resp = self.slack_client.api_call(
                'chat.postMessage',
                channel=channel,
                username=self.slack_config.get('username'),
                icon_emoji=icon,
                attachments=attachments
            )

            if not resp.get('ok'):
                raise NotificationError('Notification.send failed for channel ({c}): {e}'.format(c=channel, e=resp.get('error')))
