import requests
from datetime import datetime, timedelta
from configparser import ConfigParser

import praw
import tweepy

TEST_MODE = True

# Read config/secrets files
secrets = ConfigParser()
secrets.read('cfg/secrets.ini')

config = ConfigParser()
config.read('cfg/config.ini')

# Twitter auth
twitter = tweepy.AppAuthHandler(consumer_key=secrets['Twitter']['CONSUMER_KEY'], 
                             consumer_secret=secrets['Twitter']['CONSUMER_SECRET'])
api = tweepy.API(twitter)

# Get last 20 tweets
tweets = api.user_timeline(screen_name='Sora_Sakurai', count=200, include_rts=False, exclude_replies=True)

# Filter last 200 tweets that only contain media and after 5:00 UTC of previous day, store in dict { date : media_url }
media_files = set()
yday = (datetime.now() - timedelta(days=1)).replace(hour=5, minute=0, second=0, microsecond=0) # yesterday 5:00 UTC
for tweet in tweets:
    media = tweet.entities.get('media', [])
    text = tweet.text # format is "{tweet} {url}"; if no {tweet} then result is "{url}"
    date = tweet.created_at
    if (len(media) > 0 and not (' ' in text) and date > yday):
        tweet_url = media[0].get('url')
        media_url = media[0].get('media_url_https')
        media_files.add((tweet_url, media_url, date))
        
# Reddit auth
reddit = praw.Reddit(client_id=secrets['Reddit']['CLIENT_ID'],
                     client_secret=secrets['Reddit']['CLIENT_SECRET'],
                     user_agent=secrets['Reddit']['USER_AGENT'],
                     username=secrets['Reddit']['USERNAME_TEST' if TEST_MODE else 'USERNAME'],
                     password=secrets['Reddit']['PASSWORD'])

subreddit = reddit.subreddit(config['Reddit']['SUBREDDIT_TEST' if TEST_MODE else 'SUBREDDIT'])

# Iterate over filtered tweets to post to imgur/reddit, store in list outside scope
submissions = []
for tweet_url, media_url, date in media_files:
    date_string = datetime.strftime(date, '%m/%d/%Y')
    title = 'New Smash Pic-of-the-Day! ({}) from @Sora_Sakurai'.format(date_string)
    
    # Imgur upload
    headers = {'Authorization': 'Client-ID ' + secrets['Imgur']['CLIENT_ID']}
    data = {'title': title,
            'image': media_url,
            'type': 'URL'}
    request = requests.post(config['Imgur']['UPLOAD_API'], data=data, headers=headers)
    imgur_url = request.json()['data']['link']
    
    # Reddit upload
    submission = subreddit.submit(title=title, url=imgur_url, flair_id=None if TEST_MODE else config['Reddit']['FLAIR_ID'])
    
    # Comment
    comment = 'Tweet: [{tweet_url}]({tweet_url})\nTwitter: [@Sora_Sakurai](https://twitter.com/sora_sakurai)\nInspired by my dad: /u/SakuraiBot'.format(tweet_url)
    submission.reply(comment)
    submissions.append([submission, comment])