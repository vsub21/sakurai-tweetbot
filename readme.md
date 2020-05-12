# sakurai-tweetbot
Reddit bot for [/r/smashbros](https://www.reddit.com/r/smashbros/). Fetches new [Sakurai](https://twitter.com/sora_sakurai) pic-of-the-day from Twitter, uploads picture to Imgur, and posts to Reddit via [/u/SakuraiTweetBot](https://www.reddit.com/user/sakuraitweetbot).

Inspired by WiWiWeb's [SakuraiBot](https://github.com/Wiwiweb/SakuraiBot-Ultimate).

To use the video upload option, you must have [FFmpeg](https://www.ffmpeg.org/) installed and added to your PATH variable.

### To-do:
- Move to Azure Functions
- Remove dependency on ffmpeg
  - Check out using opencv or preferably different/smaller library
- Reupload album on imgur to bypass false-positive NSFW filter
- Add support for Sakurai replies