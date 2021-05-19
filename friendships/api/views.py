from rest_framework import viewsets, status
from django.contrib.auth.models import User
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from friendships.models import Friendship
from friendships.api.serializers import (
    FollowerSerializer,
    FollowingSerializer,
    FriendshipSerializerForCreate,
)


class FriendshipViewSet(viewsets.GenericViewSet):
    # POST /api/friendship/1/follow to follow user whose id = 1
    # the queryset here must be User.objects.all()
    # if use Friendship.objects.all() will return 404 not found
    # it because when file a request with details=True, it will call get_object()
    # which essentially calling objects.filter(pk=1) to check if the corresponding object exists
    queryset = User.objects.all()

    @action(methods=['GET'], detail=True, permission_classes=[AllowAny])
    def followers(self, request, pk):
        friendships = Friendship.objects.filter(to_user_id=pk).order_by('-created_at')
        serializer = FollowerSerializer(friendships, many=True)
        return Response(
            {'followers': serializer.data},
            status=status.HTTP_200_OK,
        )

    @action(methods=['GET'], detail=True, permission_classes=[AllowAny])
    def followings(self, request, pk):
        friendships = Friendship.objects.filter(from_user_id=pk).order_by('-created_at')
        serializer = FollowingSerializer(friendships, many=True)
        return Response(
            {'followings': serializer.data},
            status=status.HTTP_200_OK,
        )

    @action(methods=['POST'], detail=True, permission_classes=[IsAuthenticated])
    def follow(self, request, pk):
        # return 201 with silently processing when user trying to follow the same user multiple times
        # this type of error happens frequently due to network latency
        if Friendship.objects.filter(from_user=request.user, to_user=pk).exists():
            return Response({
                'success': True,
                'duplicate': True,
            }, status=status.HTTP_201_CREATED)
        serializer = FriendshipSerializerForCreate(data={
            'from_user_id': request.user.id,
            'to_user_id': pk,
        })
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors,
            }, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response({'success': True}, status=status.HTTP_201_CREATED)

    @action(methods=['POST'], detail=True, permission_classes=[IsAuthenticated])
    def unfollow(self, request, pk):
        # convert pk from string to int
        if request.user.id == int(pk):
            return Response({
                'success': False,
                'error': 'You cannot unfollow yourself'
            }, status=status.HTTP_400_BAD_REQUEST)

        # beware of Cascading Deletion in delete() when using queryset
        # in some cases, FK will have cascade setting to remove dependency when delete related records,
        # this could cause issues when critical records get deleted due to FK relationship
        # to avoid this, set on_delete=models.SET_NULL, can effectively preventing delete data we don't intended to
        deleted, _ = Friendship.objects.filter(
            from_user=request.user,
            to_user=pk,
        ).delete()

        return Response({'success': True, 'deleted': deleted})