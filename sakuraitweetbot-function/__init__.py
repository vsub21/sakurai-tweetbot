import os
import stat
from datetime import datetime, timezone
import logging

import azure.functions as func

from . import sakuraitweetbot

def main(mytimer: func.TimerRequest) -> None:
    # Logger setup
    logging.basicConfig(
        filename='{}/logs/{}{}.log'.format(sakuraitweetbot.cwd_path, datetime.today().strftime("%Y-%m-%d"),'_test' if sakuraitweetbot.TEST_MODE else ''),
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

    # Check if ffmpeg binary is executable, modify chmod if not
    ffmpeg_stat = os.stat(sakuraitweetbot.FFMPEG_PATH)
    if (ffmpeg_stat | stat.S_IXUSR) != ffmpeg_stat:
        os.chmod(sakuraitweetbot.FFMPEG_PATH, (ffmpeg_stat & stat.S_IXUSR))

    # Run sakuraitweetbot main
    sakuraitweetbot.main()

if __name__ == '__main__':
    main()