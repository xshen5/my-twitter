from django.utils.decorators import method_decorator
from rest_framework import viewsets
from rest_framework import permissions
from rest_framework.response import Response
from utils.paginations import EndlessPagination
from tweets.models import Tweet
from tweets.api.serializers import (
    TweetSerializer,
    TweetSerializerForCreate,
    TweetSerializerForDetail,
)
from newsfeeds.services import NewsFeedService
from utils.decorators import required_params
from tweets.services import TweetService
from ratelimit.decorators import ratelimit

class TweetViewSet(viewsets.GenericViewSet, ):
    """
    API endpoint that allows user to create tweets and list tweets
    """
    queryset = Tweet.objects.all()
    serializer_class = TweetSerializerForCreate
    pagination_class = EndlessPagination

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    @method_decorator(ratelimit(key='user_or_ip', rate='5/s', method='POST', block=True))
    @method_decorator(ratelimit(key='user_or_ip', rate='1/m', method='POST', block=True))
    def create(self, request, *args, **kwargs):
        """
        overload create function, to default the login user as a tweet.user
        """
        serializer = TweetSerializerForCreate(
            data=request.data,
            context={'request': request},
        )

        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Please check input',
                'errors': serializer.errors,
            }, status=400)
        tweet = serializer.save()
        NewsFeedService.fanout_to_followers(tweet)
        serializer = TweetSerializer(tweet, context={'request': request})
        return Response(serializer.data, status=201)

    @required_params(params=['user_id'])
    def list(self, request, *args, **kwargs):
        """
        overloading list function, make user_id as a requirement to filter
        """

        user_id = request.query_params['user_id']
        tweets = Tweet.objects.filter(user_id=user_id).prefetch_related('user')

        cached_tweets = TweetService.get_cached_tweets(user_id)
        page = self.paginator.paginate_cached_list(cached_tweets, request)
        if page is None:
            """
                            if 'user_id' not in request.query_params:
                        return Response('missing user_id', status=400)
                    The above line will be interpreted as following SQL:'
                    select * from twitter_tweets where user_id=xxx order by created_at DESC
                    this SQL query will be using composite index of user_id and created_at
                    """
            queryset = Tweet.objects.filter(user_id=user_id).order_by('-created_at')
            page = self.paginate_queryset(queryset)
        serializer = TweetSerializer(
            page,
            context={'request': request},
            many=True,
        )
        # usually response in JSON format should be included in hash
        # instead of a list
        return self.get_paginated_response(serializer.data)

    @method_decorator(ratelimit(key='user_or_ip', rate='5/s', method='GET', block=True))
    def retrieve(self, request, *args, **kwargs):
        serializer = TweetSerializerForDetail(
            self.get_object(),
            context={'request': request},
        )
        return Response(serializer.data)
