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

    # Check if ffmpeg binary is executable, modify chmod if not
    # ffmpeg_stat = os.stat(sakuraitweetbot.FFMPEG_PATH).st_mode
    # logger.info('ffmpeg_stat: {}'.format(ffmpeg_stat))
    # if (ffmpeg_stat | stat.S_IXUSR) != ffmpeg_stat:
    #     # os.chmod(sakuraitweetbot.FFMPEG_PATH, (ffmpeg_stat & stat.S_IXUSR)) # not working in azure functions
    #     chmod_result = os.popen("chmod u+x {}".format(sakuraitweetbot.FFMPEG_PATH)).read()
    #     logger.info('chmod_result: '.format(chmod_result))

    # Give ffmpeg 777 perms

    chmod_before_string = "ls -la {}".format(str(sakuraitweetbot.FFMPEG_PATH))
    chmod_before_res = os.popen(chmod_before_string).read()

    logger.info('Executed: "{}"'.format(chmod_before_string))
    logger.info('Output: "{}"'.format(chmod_before_res))

    chmod_string = "chmod 777 {}".format(str(sakuraitweetbot.FFMPEG_PATH))
    chmod = os.popen(chmod_before_string).read()
    logger.info('Executed: "{}"'.format(chmod_string))

    chmod_after_string = "ls -la {}".format(str(sakuraitweetbot.FFMPEG_PATH))
    chmod_after_res = os.popen(chmod_after_string).read()

    logger.info('Executed: "{}"'.format(chmod_after_string))
    logger.info('Output: "{}"'.format(chmod_after_res))

    # Run sakuraitweetbot main
    sakuraitweetbot.main()

if __name__ == '__main__':
    main()