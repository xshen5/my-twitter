from celery import shared_task
from friendships.services import FriendshipService
from newsfeeds.models import NewsFeed
from newsfeeds.constants import FANOUT_BATCH_SIZE
from utils.time_constants import ONE_HOUR


@shared_task(routing_key='newsfeeds', time_limit=ONE_HOUR)
def fanout_newsfeeds_batch_task(tweet_id, follower_ids):
    from newsfeeds.services import NewsFeedService
    newsfeeds = [
        NewsFeed(user_id=follower_id, tweet_id=tweet_id)
        for follower_id in follower_ids
        # notice here the tweet.user is the creator of tweet
    ]
    NewsFeed.objects.bulk_create(newsfeeds)

    # bulk create will not invoke post_save signal, manually push newsfeed into cache
    for newsfeed in newsfeeds:
        NewsFeedService.push_newsfeed_to_cache(newsfeed)
    return "{} newsfeeds created".format(len(newsfeeds))

@shared_task(routing_key='default', time_limit=ONE_HOUR)
def fanout_newsfeeds_main_task(tweet_id, tweet_user_id):
    # fonout the newsfeed to poster
    NewsFeed.objects.create(user_id=tweet_user_id, tweet_id=tweet_id)

    # fanout newsfeed to followers in batch
    followers_ids = FriendshipService.get_follower_ids(tweet_user_id)
    index = 0
    while index < len(followers_ids):
        batch_ids = followers_ids[index: index + FANOUT_BATCH_SIZE]
        fanout_newsfeeds_batch_task.delay(tweet_id, batch_ids)
        index += FANOUT_BATCH_SIZE

    return '{} newsfeeds going to fanout, {} batches created.'.format(
        len(followers_ids),
        (len(followers_ids) - 1) // FANOUT_BATCH_SIZE + 1,
    )