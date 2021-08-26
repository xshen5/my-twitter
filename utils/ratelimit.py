from rest_framework.views import exception_handler as drf_exception_handler
from ratelimit.exceptions import Ratelimited

def exception_handler(exc, context):
    # Call Rest framwork's default exception handler first
    # to get the standard error response
    response = drf_exception_handler(exc, context)

    # now add the HTTP status code to the response
    if isinstance(exc, Ratelimited):
        response.data['detils'] = 'Too many requests, try again later.'
        response.status_code = 429
    return response