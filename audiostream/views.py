import redis
from django.http import HttpResponse
from django_grip import set_hold_stream

r = redis.Redis()

def home(request):
	body = ''.join(reversed(r.lrange('bufs', 0, -1)))
	set_hold_stream(request, 'audio')
	return HttpResponse(body, content_type='audio/mpeg')
