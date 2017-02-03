from django.http import HttpResponse
from django_grip import set_hold_stream

def home(request):
	set_hold_stream(request, 'audio')
	return HttpResponse()
