import os
import requests
import uuid
import json
import urllib
import pathlib
import logging
import glob
from PIL import Image
from datetime import datetime, timedelta
import time
from configparser import ConfigParser

import praw
import tweepy
import ffmpeg

# Flight variables
TEST_MODE = os.environ['TEST_MODE'] == 'True'

# Get path for parent directory (PathLike)
parent = pathlib.Path(__file__).parent

# Path for temp folder in Azure Functions (Linux)
tmp = pathlib.Path("/tmp")

# Read config files
config = ConfigParser()
config.read(parent / 'cfg/config.ini')

# FFMPEG path (PathLike)
FFMPEG_PATH = parent / '../bin/ffmpeg-git-20200504-amd64-static/ffmpeg'
TMP_FFMPEG_PATH = "/tmp/ffmpeg"

logger = logging.getLogger(__name__)

def cleanup_media():
    pics = glob.glob(str(tmp / '*.jpg')) # glob doesn't accept PathLike, see: https://bugs.python.org/issue35453
    vids = glob.glob(str(tmp / '*.mp4'))
    to_delete = pics + vids
    for fp in to_delete:
        try:
            os.remove(fp)
            logger.info('Removed file: {}'.format(fp))
        except Exception as ex:
            logger.info('Error while deleting file: {}'.format(fp))
            logger.exception(ex)
            continue

def post_image_to_reddit(subreddit, media_url, title):
    # Download image
    image_fp = tmp / 'image.jpg'
    urllib.request.urlretrieve(media_url, image_fp) # accepts PathLike

    # Reddit upload
    return subreddit.submit_image(title=title, image_path=image_fp, flair_id=None if TEST_MODE else config['Reddit']['FLAIR_ID'])

def create_video_from_urls(media_urls):
    # Download images
    last_idx = 0
    for idx, media_url in enumerate(media_urls):
        image_fp = tmp / 'image-{}.jpg'.format(str(idx).zfill(3))
        if idx == 0:
            thumbnail_path = image_fp
        urllib.request.urlretrieve(media_url, image_fp) # accepts PathLike
        logger.info('Downloaded image {}.'.format(image_fp))
        last_idx = idx
        
    # ffmpeg conversion
    image_seq_fp = str(tmp / 'image-%03d.jpg') # TODO: need to check if ffmpeg.input accepts PathLike, see: https://github.com/kkroening/ffmpeg-python/issues/364
    video_fp = str(tmp / 'video.mp4')

    # Create black frame for end of video (hypothesizing Reddit cuts last still frame in video)
    size = Image.open('image-001.jpg').size
    black = Image.new('RGB', size)
    black_fp = tmp / 'image-{}.jpg'.format(str(last_idx).zfill(3))
    black.save(black_fp, "PNG")

    # Equivalent to cmd line: "{TMP_FFMPEG_PATH} -loop 1 -i {image_seq_fp} -t 10 {video_fp} -framerate 1/5"
    out, err = ffmpeg.input(image_seq_fp, loop=1, t=10, framerate=1/5).output(video_fp).run(cmd=TMP_FFMPEG_PATH, quiet=True)

    logger.info('ffmpeg stdout: {}'.format(out))
    logger.info('ffmpeg stderr: {}'.format(err))

    return video_fp, thumbnail_path

def post_gallery_to_reddit(subreddit, media_urls, title):
    tmp = pathlib.Path('/tmp')
    last_idx = 0
    image_fps = []
    for idx, media_url in enumerate(media_urls):
        image_fp = tmp / 'image-{}.jpg'.format(idx)
        urllib.request.urlretrieve(media_url, image_fp) # accepts PathLike
        image_fps.append(image_fp)
        logger.info('Downloaded image {}.'.format(image_fp))

    images = [{'image_path': image_fp} for image_fp in image_fps]
    title += ' ({} images!)'.format(len(media_urls))
    submission = subreddit.submit_gallery(title=title, images=images, flair_id=None if TEST_MODE else config['Reddit']['FLAIR_ID'])
    logger.info('Reddit gallery submission: {}'.format(submission.__dict__))
    return submission

def post_video_to_reddit(subreddit, media_urls, title):
    video_fp, thumbnail_path = create_video_from_urls(media_urls)
    title += ' ({} images!)'.format(len(media_urls))
    submission = subreddit.submit_video(title=title, video_path=video_fp, videogif=False, thumbnail_path=thumbnail_path, flair_id=None if TEST_MODE else config['Reddit']['FLAIR_ID'])
    logger.info('Reddit video submission: {}'.format(submission.__dict__))
    return submission

def post_link_to_reddit(subreddit, url, title):
    submission = subreddit.submit(title=title, url=url, flair_id=None if TEST_MODE else config['Reddit']['FLAIR_ID'])
    logger.info('Reddit link submission: {}'.format(submission.__dict__))
    return submission

def translate_text(text_list):
    # Check https://docs.microsoft.com/en-us/azure/cognitive-services/translator/quickstart-translator?tabs=python for reference
    api_key = os.environ['AZURE_TRANSLATOR_API_KEY']
    region = os.environ['AZURE_REGION']
    endpoint = config['Azure']['TRANSLATE_ENDPOINT']

    params = {
        'api-version': '3.0',
        'from': 'ja',
        'to': 'en'
    }

    headers = {
        'Ocp-Apim-Subscription-Key': api_key,
        'Ocp-Apim-Subscription-Region' : region,
        'Content-type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }

    body = [{'text': text} for text in text_list]
    logger.info('Request body: {}'.format(body))

    request = requests.post(endpoint, params=params, headers=headers, json=body)

    response = request.json()
    logger.info('Translations: {}'.format(response))

    translations = [res['translations'][0]['text'] for res in response]

    return translations

def create_reddit_comment(tweet_url, media_urls, text_list, submission):
    comment = '[Original Tweet]({}) and '.format(tweet_url)
    
    if len(media_urls) > 1:
        # TODO: figure out a better way to do this possibly with map/lambda and str join
        comment += 'Full-Size Images!: '
        for idx, media_url in enumerate(media_urls):
            comment += '[Image {}]({}), '.format(idx + 1, media_url) # 1-index
        comment = comment[:-2] + '\n\n' # removes trailing ', '
    else:
        comment += '[Full-Size Image!]({})\n\n'.format(media_urls[0])

    if text_list:
        translations = translate_text(text_list)
        if len(translations) > 1:
            for idx, translation in enumerate(translations):
                comment += 'Tweet {} Text:\n\n'.format(idx + 1) # 1-index
                comment += '> {}\n\n'.format(text_list[idx])
                comment += 'Translation:\n\n'
                comment += '> {}\n\n'.format(translation)
        elif len(translations) == 1:
            comment += 'Tweet Text:\n\n'
            comment += '> {}\n\n'.format(text_list[0])
            comment += 'Translation:\n\n'
            comment += '> {}\n\n'.format(translations[0])
    
    comment += 'Twitter: [@Sora_Sakurai](https://twitter.com/sora_sakurai)\n\n'
    comment += 'Inspired by my dad: /u/SakuraiBot\n\n'
    comment += '[Album of all Smash Pics-of-the-Day!](https://imgur.com/a/{})'.format(os.environ['IMGUR_ALBUM_ID'])
    comment += '\n\n---\n*^I ^am ^a ^bot, ^and ^this ^action ^was ^performed ^automatically. ^Message ^[me](https://www.reddit.com/message/compose?to=%2Fu%2FSakuraiTweetBot) ^if ^you ^have ^any ^questions ^or ^concerns. ^For ^information ^about ^me, ^visit ^this ^[thread](https://www.reddit.com/r/smashbros/comments/exewn8/introducing_sakuraitweetbot_posting_sakurai/) ^(here.)*\n\n'

    if text_list:
        comment += '*^Translated ^using ^([Microsoft Azure Translator](https://azure.microsoft.com/en-us/services/cognitive-services/translator/).)*'
    
    reply = submission.reply(comment)
    logger.info('Reddit reply: {}'.format(reply.__dict__))
    return reply

def create_imgur_post(media_url, title, tweet_url, idx, num_images):
    if num_images > 1:
        title = title + ' (Image {})'.format(idx + 1) # 1-indexed when displaying
    headers = {'Authorization': 'Bearer ' + os.environ['IMGUR_ACCESS_TOKEN']}
    data = {'title': title,
            'image': media_url,
            'description': 'Original Tweet: {}'.format(tweet_url).replace('.', '&#46;'), # imgur bug workaround, see https://github.com/DamienDennehy/Imgur.API/issues/8
            'type': 'URL'}
    logger.info('data for CREATE_IMGUR_POST POST request: {}'.format(data))

    MAX_ATTEMPTS = 5
    for i in range(0, MAX_ATTEMPTS):
        request = requests.post(config['Imgur']['UPLOAD_IMAGE_API'], data=data, headers=headers)
        json = request.json()
        logger.info('JSON for CREATE_IMGUR_POST POST request, attempt #{}:\n{}'.format(i + 1, json)) # 1-index attempts
        if json['success']:
            break
        else:
            if (i == MAX_ATTEMPTS - 1):
                logger.warning('Failed POST request after {} attempts. Terminating.'.format(MAX_ATTEMPTS))
            else:
                logger.info('Failed POST request, attempt #{}, retrying... ({} max attempts)'.format(i + 1, MAX_ATTEMPTS)) # 1-index attempts
                if os.environ['SLEEP_MODE'] == 'True':
                    time.sleep(90) # sleep for 90 seconds; find better way to do this, not ideal.

    image_id = json['data']['id']
    image_url = json['data']['link']

    return image_id, image_url

def create_imgur_album():
    headers = {'Authorization': 'Bearer ' + os.environ['IMGUR_ACCESS_TOKEN']}
    data = {'title': 'New Smash Pic-of-the-Day Album! by /u/SakuraiTweetBot',
            'description': 'An album containing each Smash pic-of-the-day posted by @Sora_Sakurai on Twitter, mirrored to /r/smashbros on Reddit by /u/SakuraiTweetBot.',
            'privacy': 'public'       
        }
    logger.info('data for CREATE_IMGUR_ALBUM POST request: {}'.format(data))
    request = requests.post(config['Imgur']['CREATE_ALBUM_API'], data=data, headers=headers)

    json = request.json()
    logger.info('JSON for CREATE_IMGUR_ALBUM POST request:\n{}'.format(json))

    album_hash = json['data']['id']
    return album_hash

def update_imgur_album(image_ids):
    headers = {'Authorization': 'Bearer ' + os.environ['IMGUR_ACCESS_TOKEN']}
    # GET request to get ids of images in album in order
    request = requests.get(config['Imgur']['CREATE_ALBUM_API'] + '/{}/images'.format(os.environ['IMGUR_ALBUM_ID']), headers=headers)
    
    album_ids = [image['id'] for image in request.json()['data']]
    logger.info('album_ids from UPDATE_IMGUR_ALBUM GET request: {}'.format(album_ids))

    album_ids = image_ids + album_ids # prepend new images to list

    # POST request to set image ids in album
    data = {'ids[]': album_ids}

    request = requests.post(config['Imgur']['CREATE_ALBUM_API'] + '/{}/'.format(os.environ['IMGUR_ALBUM_ID']), data=data, headers=headers)
    logger.info('data for UPDATE_IMGUR_ALBUM POST request: {}'.format(data))

    json = request.json()
    logger.info('JSON for UPDATE_IMGUR_ALBUM POST request:\n{}'.format(json))

    # PUT request to update cover to id of top of album
    data = {'cover': album_ids[0]}

    request = requests.put(config['Imgur']['CREATE_ALBUM_API'] + '/{}'.format(os.environ['IMGUR_ALBUM_ID']), data=data, headers=headers)
    logger.info('data for UPDATE_IMGUR_ALBUM PUT request: {}'.format(data))

    json = request.json()
    logger.info('JSON for UPDATE_IMGUR_ALBUM PUT request:\n{}'.format(json))

def post_to_imgur_gallery(image_ids, title):
    headers = {'Authorization': 'Bearer ' + os.environ['IMGUR_ACCESS_TOKEN']}
    # POST request to add image_ids to imgur public gallery
    data = {'title': title,
            'terms': 1,
            'mature': 0,
            'tags':'smashbros'}
    logger.info('data for POST_TO_IMGUR_GALLERY POST request: {}'.format(data))
    request = requests.post(config['Imgur']['UPLOAD_IMAGE_GALLERY'] + '/{}'.format(iid), data=data, headers=headers)
    json = request.json()
    logger.info('JSON for POST_TO_IMGUR_GALLERY POST POST request:\n{}'.format(json))

def main():
    logger.info('TEST_MODE={}'.format(TEST_MODE))

    # Cleanup media before start
    cleanup_media()
    logger.info('Cleaned up media.')

    try:
        # Twitter auth
        twitter = tweepy.AppAuthHandler(consumer_key=os.environ['TWITTER_CONSUMER_KEY'], 
                                    consumer_secret=os.environ['TWITTER_CONSUMER_SECRET'])
        logger.info('Twitter auth complete.')
        api = tweepy.API(twitter)

        # Get last 200 tweets
        SCREEN_NAME = 'Sora_Sakurai'
        TWEET_COUNT = 200
        tweets = api.user_timeline(screen_name=SCREEN_NAME, count=TWEET_COUNT, include_rts=False, exclude_replies=False)
        logger.info('Fetched last {} tweets from @{}.'.format(TWEET_COUNT, SCREEN_NAME))

        # Filter last 200 tweets after 5:00 UTC of previous day that only contain media and store in set (tweet_url, media_url, date)
        media_files = []

        # Posting time usually at 11:00 PM EDT (3:00 UTC)
        lower = datetime.utcnow().replace(hour=2, minute=30, second=0, microsecond=0) # yesterday 22:30/10:30 PM EDT, today 2:30 UTC
        upper = lower + timedelta(hours=1, minutes=45)
        logger.info('Lower bound time constraint: {}'.format(lower))
        logger.info('Upper bound time constraint: {}'.format(upper))

        tweet_ids = set()
        # TODO: Integrate reply parsing properly; get rid of this below and the hacky way of extracting pictures from replies, use tweet.id and tweet.in_reply_to_status_id
        # tweets is ordered by newest to oldest; in order to get Sakurai's reply tweets that have no media, need to check if tweet.in_reply_to_status_id is in tweet_ids set
        for tweet in reversed(tweets):
            date = tweet.created_at
            if (date > lower and date < upper):
                media = tweet.entities.get('media', [])
                text = tweet.text # format is "{tweet} {url}", note the space; if no {tweet} then result is just "{url}" --- for media tweets; for text tweets, no url is present
                if len(media) > 0:
                    tweet_url = 'https://twitter.com/Sora_Sakurai/status/{}'.format(tweet.id)
                    media_urls = ['{}?format=jpg&name=4096x4096'.format(med.get('media_url_https')) for med in tweet.extended_entities['media']] # for when more than one image to a tweet
                    if ' ' not in text:
                        text_list = [] # provide empty list
                    else:
                        text_list = [text.rsplit(' ', 1)[0]] # remove url so tweet extracted is just the text; when tweet has media, text also contains shortened url appended
                    media_files.append((tweet_url, media_urls, text_list, date))
                    tweet_ids.add(tweet.id)
                elif tweet.in_reply_to_status_id in tweet_ids:
                    tweet_url = 'https://twitter.com/Sora_Sakurai/status/{}'.format(tweet.id)
                    media_urls = []
                    text_list = [text.rsplit(' ', 1)[0]]
                    media_files.append((tweet_url, media_urls, text_list, date))
                    tweet_ids.add(tweet.id)
        media_files.reverse()
        logger.info('Filtered tweets set: {}'.format(media_files))

        # Reddit auth
        reddit = praw.Reddit(client_id=os.environ['REDDIT_CLIENT_ID'],
                            client_secret=os.environ['REDDIT_CLIENT_SECRET'],
                            user_agent=os.environ['REDDIT_USER_AGENT'],
                            username=os.environ['REDDIT_USERNAME_TEST' if TEST_MODE else 'REDDIT_USERNAME'],
                            password=os.environ['REDDIT_PASSWORD'])
        logger.info('Reddit auth complete.')

        subreddit = reddit.subreddit(config['Reddit']['SUBREDDIT_TEST' if TEST_MODE else 'SUBREDDIT'])
        logger.info('Using subreddit: {}'.format(subreddit))

        # Iterate over filtered tweets to post to imgur/reddit, store in list outside scope
        submissions = []

        # Quick and hacky/dirty way to consolidate all pics into one post if extra tweets (i.e. in a reply)
        if (len(media_files) > 1):
            media_files.reverse() # if more than one tweet, most likely a reply in which case API returns most recent first -- should reverse for picture ordering
            # Extract all other media_urls in other tweets and place in first media_files url list
            for _, media_urls, text_list, _ in media_files[1:]:
                media_files[0][1].extend(media_urls)
                media_files[0][2].extend(text_list)
            media_files = [media_files[0]] # remove all other tweets -- can fix this whole process later...

        for tweet_url, media_urls, text_list, date in media_files:
            date_string = datetime.strftime(date, '%m/%d/%Y')
            base_title = 'New Smash Pic-of-the-Day! ({}) from @Sora_Sakurai'.format(date_string)

            image_uploads = []
            num_images = len(media_urls)
            for idx, media_url in enumerate(media_urls): # post images to imgur
                upload = create_imgur_post(media_url, base_title, tweet_url, idx, num_images)
                image_uploads.append(upload)
            if num_images > 1:
                submission = post_gallery_to_reddit(subreddit, media_urls, base_title) # post gallery to reddit
                cleanup_media()
            else: # only one image in tweet
                image_url = image_uploads[0][1]
                submission = post_link_to_reddit(subreddit, image_url, base_title) # post link to imgur post       
            
            image_ids = [iid for iid, url in image_uploads]
            
            if not TEST_MODE:
                update_imgur_album(image_ids)
            
            # Create Reddit comment
            reply = create_reddit_comment(tweet_url, media_urls, text_list, submission)

            # Sticky and mod distinguish
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

if __name__ == '__main__':
    main()