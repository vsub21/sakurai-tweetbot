import os
import requests
import urllib
import logging
from datetime import datetime, timedelta
from configparser import ConfigParser

import praw
import tweepy
import ffmpeg

# Flight variables
TEST_MODE = True
POST_MODE = 'imgur' # 'imgur', 'image' (reddit), 'video' (reddit), or 'tweet'
HAS_MOD = True

# Read config/secrets files
secrets = ConfigParser()
secrets.read('cfg/secrets.ini')

config = ConfigParser()
config.read('cfg/config.ini')

# Logger setup
logging.basicConfig(
    filename='{}/logs/{}{}.log'.format(secrets['Local']['repo_path'], datetime.today().strftime("%Y-%m-%d"),'_test' if TEST_MODE else ''),
    filemode='w',
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%m/%d/%Y %I:%M:%S %p',
    level=logging.DEBUG
)

logger = logging.getLogger(__name__)

logger.info('TEST_MODE={}'.format(TEST_MODE))
logger.info('POST_MODE={}'.format(POST_MODE))
logger.info('HAS_MOD={}'.format(HAS_MOD))

try:
    # Twitter auth
    twitter = tweepy.AppAuthHandler(consumer_key=secrets['Twitter']['CONSUMER_KEY'], 
                                consumer_secret=secrets['Twitter']['CONSUMER_SECRET'])
    logger.info('Twitter auth complete.')
    api = tweepy.API(twitter)

    # Get last 200 tweets
    SCREEN_NAME = 'Sora_Sakurai'
    TWEET_COUNT = 200
    tweets = api.user_timeline(screen_name=SCREEN_NAME, count=TWEET_COUNT, include_rts=False, exclude_replies=True)
    logger.info('Fetched last {} tweets from @{}.'.format(TWEET_COUNT, SCREEN_NAME))

    # Filter last 200 tweets after 5:00 UTC of previous day that only contain media and store in set (tweet_url, media_url, date)
    media_files = set()
    yday = (datetime.utcnow() - timedelta(days=1)).replace(hour=5, minute=0, second=0, microsecond=0) # yesterday 5:00 UTC
    logger.info('Lower bound constraint: {}')
    for tweet in tweets:
        media = tweet.entities.get('media', [])
        text = tweet.text # format is "{tweet} {url}"; if no {tweet} then result is "{url}"
        date = tweet.created_at
        if (date > yday and len(media) > 0 and not (' ' in text)):
            tweet_url = media[0].get('expanded_url')
            media_url = '{}?format=jpg&name=4096x4096'.format(media[0].get('media_url_https'))
            media_files.add((tweet_url, media_url, date))
    logger.info('Filtered tweets set: {}'.format(media_files))

    # Reddit auth
    reddit = praw.Reddit(client_id=secrets['Reddit']['CLIENT_ID'],
                        client_secret=secrets['Reddit']['CLIENT_SECRET'],
                        user_agent=secrets['Reddit']['USER_AGENT'],
                        username=secrets['Reddit']['USERNAME_TEST' if TEST_MODE else 'USERNAME'],
                        password=secrets['Reddit']['PASSWORD'])
    logger.info('Reddit auth complete.')

    subreddit = reddit.subreddit(config['Reddit']['SUBREDDIT_TEST' if TEST_MODE else 'SUBREDDIT'])
    logger.info('Using subreddit: {}'.format(subreddit))

    # Iterate over filtered tweets to post to imgur/reddit, store in list outside scope
    submissions = []
    for tweet_url, media_url, date in media_files:
        date_string = datetime.strftime(date, '%m/%d/%Y')
        title = 'New Smash Pic-of-the-Day! ({}) from @Sora_Sakurai'.format(date_string)
        
        if HAS_MOD and POST_MODE == 'imgur': # need r/smashbros mod approval
            # Imgur upload
            headers = {'Authorization': 'Client-ID ' + secrets['Imgur']['CLIENT_ID']}
            data = {'title': title,
                    'image': media_url,
                    'type': 'URL'}
            request = requests.post(config['Imgur']['UPLOAD_API'], data=data, headers=headers)
            json = request.json()
            logger.info('Imgur request JSON: {}'.format(json))
            imgur_url = json['data']['link']

            # Reddit upload
            submission = subreddit.submit(title=title, url=imgur_url, flair_id=None if TEST_MODE else config['Reddit']['FLAIR_ID'])

        elif HAS_MOD and POST_MODE == 'image':
            # Download image
            image_fp = '{}/media/image.jpg'.format(secrets['Local']['repo_path'])
            urllib.request.urlretrieve(media_url, image_fp)

            # Reddit upload
            submission = subreddit.submit_image(title=title, image_path=image_fp, flair_id=None if TEST_MODE else config['Reddit']['FLAIR_ID'])

            # Cleanup
            try:
                os.remove(image_fp)
            except Exception as ex:
                logger.exception(ex)
                continue

        elif POST_MODE == 'video': # requires ffmpeg installation and PATH variable set
            # Download image
            image_fp = '{}/media/image.jpg'.format(secrets['Local']['repo_path'])
            urllib.request.urlretrieve(media_url, image_fp)
            logger.info('Downloaded image.')

            # ffmpeg conversion
            video_fp = '{}/media/video.mp4'.format(secrets['Local']['repo_path'])
            out, err = ffmpeg.input(image_fp, loop=1, t=10).output(video_fp).run(quiet=True) # ffmpeg -loop 1 -i {image_fp} -t 10 {video_fp}
            
            logger.info('ffmpeg stdout: {}'.format(out))
            logger.info('ffmpeg stderr: {}'.format(err))

            # Reddit upload
            submission = subreddit.submit_video(title=title, video_path=video_fp, videogif=False, thumbnail_path=image_fp, flair_id=None if TEST_MODE else config['Reddit']['FLAIR_ID'])

            # Cleanup
            try:
                os.remove(image_fp)
                os.remove(video_fp)
            except Exception as ex:
                logger.exception(ex)
                continue

        else: # assume POST_MODE == 'twitter', post link to tweet instead
            submission = subreddit.submit(title=title, url=tweet_url, flair_id=None if TEST_MODE else config['Reddit']['FLAIR_ID'])
        
        logger.info('Reddit submission ({}): {}'.format(POST_MODE, submission.__dict__))
        
        # Comment
        comment = '[Original Tweet]({}) and [Full-Size Image!]({})\n\nTwitter: [@Sora_Sakurai](https://twitter.com/sora_sakurai)\n\nInspired by my dad: /u/SakuraiBot\n\n---\n*^I ^am ^a ^bot, ^and ^this ^action ^was ^performed ^automatically. ^Message ^[me](https://www.reddit.com/message/compose?to=%2Fu%2FSakuraiTweetBot) ^if ^you ^have ^any ^questions ^or ^concerns. ^For ^information ^about ^me, ^visit ^this ^[thread](https://www.reddit.com/r/smashbros/comments/exewn8/introducing_sakuraitweetbot_posting_sakurai/) ^(here.)*'.format(tweet_url, media_url)
        reply = submission.reply(comment)
        logger.info('Reddit reply: {}'.format(reply.__dict__))
        if HAS_MOD: # sticky and mod distinguish
            submission.mod.distinguish(how='yes', sticky=False)
            submission.mod.approve()
            logger.info('Distinguished, approved submission {}'.format(submission))
            reply.mod.distinguish(how='yes', sticky=True)
            reply.mod.approve()
            logger.info('Distinguished, approved stickied comment {}'.format(reply))
        submissions.append((submission, reply))

    logger.info('Final submissions: {}'.format(submissions))

except Exception as e:
    logger.exception(e)
