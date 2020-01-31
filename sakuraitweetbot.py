import requests
from datetime import datetime, timedelta

import praw
import tweepy
from configparser import ConfigParser

TEST_MODE = True

# Read config/secrets files
secrets = ConfigParser()
secrets.read('/cfg/secrets.ini')

config = ConfigParser()
config.read('/cfg/config.ini')

# Twitter auth
twitter = tweepy.AppAuthHandler(consumer_key=secrets['Twitter']['CONSUMER_KEY'], 
                             consumer_secret=secrets['Twitter']['CONSUMER_SECRET'])
api = tweepy.API(twitter)

# Get last 20 tweets
tweets = api.user_timeline(screen_name='Sora_Sakurai', count=200, include_rts=False, exclude_replies=True)

# Filter last 200 tweets that only contain media and after 5:00 UTC of previous day, store in dict { date : media_url }
media_files = {}
yday = (datetime.now() - timedelta(days=1)).replace(hour=5, minute=0, second=0, microsecond=0) # yesterday 5:00 UTC
for tweet in tweets:
    media = tweet.entities.get('media', [])
    text = tweet.text # format is "{tweet} {url}"; if no {tweet} then result is "{url}"
    date = tweet.created_at
    if (len(media) > 0 and not (' ' in text) and date > yday):
        media_url = media[0]['media_url_https']
        media_files[date] = media_url
        
# Reddit auth
reddit = praw.Reddit(client_id=secrets['Reddit']['CLIENT_ID'],
                     client_secret=secrets['Reddit']['CLIENT_SECRET'],
                     user_agent=secrets['Reddit']['USER_AGENT'],
                     username=secrets['Reddit']['USERNAME_TEST' if TEST_MODE else 'USERNAME'],
                     password=secrets['Reddit']['PASSWORD'])

subreddit = reddit.subreddit(config['Reddit']['SUBREDDIT_TEST' if TEST_MODE else 'SUBREDDIT'])

# Iterate over filtered tweets to post to imgur/reddit, store in list outside scope
submissions = []
for date, url in media_files.items():
    date_string = datetime.strftime(date, '%m/%d/%Y')
    title = 'New Smash Pic-of-the-Day! ({}) from @Sora_Sakurai'.format(date_string)
    
    # Imgur upload
    if TEST_MODE:
        headers = {'Authorization': 'Client-ID ' + secrets['Imgur']['CLIENT_ID']}
    else:
        headers = {'Authorization': 'Bearer ' + secrets['Imgur']['CLIENT_SECRET']}

    data = {'title': title,
            'image': url,
            'type': 'URL'}
    request = requests.post(config['Imgur']['UPLOAD_API'], data=data, headers=headers)
    imgur_url = request.json()['data']['link']
    
    # Reddit upload
    submission = subreddit.submit(title=title, url=imgur_url, flair_id=None if TEST_MODE else config['Reddit']['FLAIR_ID'])
    
    # Comment on submission
    comment = """Twitter: [@Sora_Sakurai](https://twitter.com/sora_sakurai)
    Inspired by my dad: /u/SakuraiBot
    """
    submission.reply(comment)

    submissions.append([submission, comment])