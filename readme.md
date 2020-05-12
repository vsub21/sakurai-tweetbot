# sakurai-tweetbot
![deploy](https://github.com/vsub21/sakurai-tweetbot/workflows/deploy/badge.svg)

Reddit bot for [/r/smashbros](https://www.reddit.com/r/smashbros/). Fetches new [Sakurai](https://twitter.com/sora_sakurai) pic-of-the-day from Twitter, uploads picture to Imgur, and posts to Reddit via [/u/SakuraiTweetBot](https://www.reddit.com/user/sakuraitweetbot).

Inspired by WiWiWeb's [SakuraiBot](https://github.com/Wiwiweb/SakuraiBot-Ultimate).

Currently deployed on Azure Functions.

## To-do:
- Fix logging statements on Azure to include debug level statements
- Research what can be removed from ffmpeg binaries folder (i.e. model/, ffprobe, etc.)