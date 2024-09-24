""" Sends text notifications to a TAK server as a chat message """

import time
from tak_chat_formatter import TakChatFormatter
import tak_connection


class NotifierFunctor(TakChatFormatter):
    """Sends a string notification to TAK server as a chat message"""

    def __init__(self, config):
        super().__init__(config)
        self.config = config
        self.__setup()

    def __setup(self):
        tak_connection.create_tak_connection(self.config)
        time.sleep(2)
        self(self.config, "TakNotifier - Active", "0", 0, "", "control", "")
        self(self.config, "TakNotifier - Active", "1", 0, "", "control", "")
        self(self.config, "TakNotifier - Active", "2", 0, "", "control", "")

    def __call__(self, config, title, msg_text, priority, alert_type_name, sound, url):
        tak_notifier_alert_on = config.get("tak_notifier_alert_on", [])
        if ("control" == alert_type_name) or ("*" in tak_notifier_alert_on) or (alert_type_name in tak_notifier_alert_on):
            content = f"{title}||{msg_text}"
            # msg=self.__customize_template(config,content)
            msg = self.format_chat_msg(content)
            print("############################################")
            print(msg)
            print("############################################")
            # self.connection.send(msg.encode("utf-8"))
            try:
                tak_connection.send_to_tak(msg.encode("utf-8"))
            except ConnectionError as ce:
                print(ce)
                self.__setup()
