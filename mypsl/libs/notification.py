
import os
import ConfigParser
import time
import smtplib
from email.mime.text import MIMEText
from slackclient import SlackClient
from .exceptions import NotificationError

import pprint

pp = pprint.PrettyPrinter(indent=4)

SUPPORTED_NOTIFICATION_TYPES = ('email', 'slack')

'''
NOTE: There can be more than one slack channel. They must be separated by a comma.
----------------------------------------
`~/.slack_auth`
[slack]
username: jazzcibot
token: theSuperSecretToken
channels: #tech-jazzbot-noise,#second-optional-channelname
'''


class Notification(object):

    def __init__(self, proxies = None):
        self.proxies = proxies
        self.slack_config = None

        self.notification_type = os.getenv('NOTIFICATION_TYPE', None)

        if not self.notification_type or self.notification_type not in SUPPORTED_NOTIFICATION_TYPES:
            _m = '\n'.join(' - {t}'.format(t=t) for t in SUPPORTED_NOTIFICATION_TYPES)
            _m = '''NOTIFICATION_TYPE environment variable not set. Supported notification types:
{tstr}
'''.format(tstr=_m)

            raise NotificationError(_m)

        self.notification_type = self.notification_type.lower()

    def send(self, msg_short, msg_long, kwargs):
        try:
            if self.notification_type == 'email':
                self.send_email(msg_short, msg_long)

            if self.notification_type == 'slack':
                self.send_slack_msg(msg_long, msg_short, kwargs)

        except NotificationError:
            # let any raised NotificationError's bubbled up pass thru.
            # This means that if we blow a TypeError, or KeyError (etc) we'll have to catch that higher up
            pass

    def send_email(self, subject, body):
        from_addr = os.getenv('NOTIFICATION_FROM', None)
        to_addr = os.getenv('NOTIFICATION_TO', None)
        smtp_host = os.getenv('NOTIFICATION_HOST', 'localhost')

        if not from_addr or not to_addr:
            raise NotificationError('Either NOTIFICATION_{FROM|TO} is not set')

        # Give it our best shot to untangle things for the email
        if isinstance(body, dict):
            new_body = '\n'.join('{k}: {v}'.format(k=key, v=val) for key, val in body.items())
        else:
            new_body = body

        try:
            msg = MIMEText(new_body)

            msg['Subject'] = subject
            msg['From'] = from_addr
            msg['To'] = to_addr

            s = smtplib.SMTP(smtp_host)
            s.sendmail(from_addr, [to_addr], msg.as_string())
            s.quit()
        except Exception as e:
            # catch anything that may have happened here (for now), and turn that
            # into a NotificationError
            raise NotificationError(e)

    def __get_slack_client(self, auth_file):
        config = ConfigParser.ConfigParser()
        config.read(auth_file)

        self.slack_config = {
            'username': config.get('slack', 'username'),
            'token': config.get('slack', 'token'),
            'channels': config.get('slack', 'channels').split(',')
        }

        return SlackClient(self.slack_config.get('token'), proxies=self.proxies)

    def send_slack_msg(self, query_data, msg, kwargs={}):

        slack_auth_file = os.path.join(os.path.expanduser('~'), '.slack_auth')

        if not os.path.exists(slack_auth_file):
            raise NotificationError('Slack auth/config file not found! {f}'.format(f=slack_auth_file))

        slack_client = self.__get_slack_client()
        channels = self.slack_config.get('channels')
        fields = []

        for key, val in query_data.items():
            fields.append({
                'title': key,
                'value': val,
                'short': False if key == 'info' else True
            })

        attachments = [{
            'color':    '#E42217',
            'fields':   fields,
            'footer':   'mypsl query killah',
            'ts':       time.time()
        }]

        for channel in channels:
            resp = slack_client.api_call(
                'chat.postMessage',
                channel=channel,
                username=self.slack_config.get('username'),
                text=msg,
                icon_emoji=kwargs['icon'] if kwargs.get('icon') else None,
                attachments=attachments
            )

            if not resp.get('ok'):
                raise NotificationError('Notification.send failed for channel ({c}): {e}'.format(c=channel, e=resp.get('error')))
