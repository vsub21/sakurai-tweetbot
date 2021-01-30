import os
import stat
from datetime import datetime, timezone
import logging

import azure.functions as func

from . import sakuraitweetbot

def main(mytimer: func.TimerRequest) -> None:
    # Logger setup
    logging.basicConfig(
        filename='/logs/{}{}.log'.format(datetime.today().strftime("%Y-%m-%d"),'_test' if sakuraitweetbot.TEST_MODE else ''),
        filemode='w',
        format='%(asctime)s %(levelname)s (%(name)s): %(message)s',
        datefmt='%m/%d/%Y %I:%M:%S %p',
        level=logging.DEBUG
    )

    logger = logging.getLogger(__name__)

    # Time check
    utc_timestamp = datetime.utcnow().replace(
        tzinfo=timezone.utc).isoformat()

    if mytimer.past_due:
        logger.info('The timer is past due!')

    logger.info('Python timer trigger function ran at {} (UTC)'.format(utc_timestamp))

    # Pass custom tweet ids as env variable string (sep==';')
    custom_tweet_ids = os.environ.get('CUSTOM_TWEET_IDS', None)
    if custom_tweet_ids:
        custom_tweet_ids = set(custom_tweet_ids.split(';'))

    # Run sakuraitweetbot main
    sakuraitweetbot.main(custom_tweet_ids)

if __name__ == '__main__':
    main()