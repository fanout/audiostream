import time
import socket
import threading
import subprocess
import zmq
import tnetstring
from django.core.management.base import BaseCommand

zmq_context = zmq.Context()

def _publish_worker():
	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	sock.bind(('127.0.0.1', 5004))

	out_sock = zmq_context.socket(zmq.PUSH)
	out_sock.connect('tcp://localhost:5560')

	buf = ''
	while True:
		data, addr = sock.recvfrom(65536)
		buf += data
		if len(buf) >= 16384:
			m = {
				'channel': 'audio',
				'formats': {
					'http-stream': {
						'content': buf
					}
				}
			}
			out_sock.send(tnetstring.dumps(m), zmq.DONTWAIT)
			buf = ''

def _play(filename):
	subprocess.check_call(['gst-launch-1.0', 'filesrc', 'location=%s' % filename, '!', 'decodebin', '!', 'queue', '!', 'audioconvert', '!', 'lamemp3enc', '!', 'udpsink', 'clients=localhost:5004'])

class Command(BaseCommand):
	help = 'Background cleanup task'

	def add_arguments(self, parser):
		parser.add_argument('filename')

	def handle(self, *args, **options):
		thread = threading.Thread(target=_publish_worker)
		thread.daemon = True
		thread.start()

		while True:
			_play(options['filename'])
			time.sleep(5)
