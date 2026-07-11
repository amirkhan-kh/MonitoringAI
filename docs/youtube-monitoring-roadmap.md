# YouTube Monitoring Roadmap

## 1. Data Sources

- Channel monitoring: official/client channels, competitor channels, creator channels.
- Video monitoring: specific videos, Shorts, campaign videos.
- Keyword and hashtag monitoring: brand names, product names, competitor terms, issue/risk phrases.
- Comment monitoring: top-level comments and available replies through YouTube Data API `commentThreads.list`.
- Video metadata: title, description, channel, publish date, views, likes, comment count.
- Future AI media layer: transcript, captions, audio/video understanding, visual brand/logo detection.

## 2. Current Implementation

- `/youtube-monitoring` page mirrors Telegram monitoring UI principles.
- YouTube sources are stored separately from Telegram sources.
- Source types supported: `channel`, `video`, `keyword`, `hashtag`.
- Monitoring modes supported: `all_messages`, `brand_matches_only`.
- Backfill/sync starts from `monitor_from`.
- `youtube-worker` continuously syncs active sources when `YOUTUBE_API_KEY` is configured.

## 3. API Strategy

- Use `channels.list` for channel ID/handle resolution.
- Use `search.list` for keyword, hashtag, and channel video discovery.
- Use `videos.list` for statistics and metadata enrichment.
- Use `commentThreads.list` for public comments and available replies.
- Keep `max_pages` low by default because YouTube quota is finite.

## 4. Analysis Layers

- Level 1: title, description, comment text sentiment and risk.
- Level 2: author repetition, repeated complaints, spam/coordinated comment patterns.
- Level 3: trend charts by channel, topic, sentiment, view/comment velocity.
- Level 4: transcript/audio AI for brand mention detection inside spoken content.
- Level 5: video frame/thumbnail AI for logo, product, scene and brand safety detection.

## 5. Practical Limits

- Comments are available only when public and not disabled.
- Some replies may require pagination beyond the first included reply set.
- YouTube does not provide a Telegram-like real-time webhook for all comment changes; polling and quota-aware scheduling are required.
- PubSub-style channel upload notifications can be added later for new video discovery, but comments still need API polling.

## 6. References

- YouTube Data API commentThreads.list: https://developers.google.com/youtube/v3/docs/commentThreads/list
- YouTube Data API channels.list: https://developers.google.com/youtube/v3/docs/channels/list
- YouTube Data API search.list: https://developers.google.com/youtube/v3/docs/search/list
- YouTube Data API videos.list: https://developers.google.com/youtube/v3/docs/videos/list
- YouTube Data API quota guide: https://developers.google.com/youtube/v3/determine_quota_cost
