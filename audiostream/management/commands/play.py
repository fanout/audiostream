import time
import socket
import threading
import subprocess
import zmq
import tnetstring
import redis
from django.core.management.base import BaseCommand

zmq_context = zmq.Context()

r = redis.Redis()

def _play(filename):
	subprocess.check_call(['gst-launch-1.0', 'filesrc', 'location=%s' % filename, '!', 'decodebin', '!', 'queue', '!', 'audioconvert', '!', 'lamemp3enc', '!', 'udpsink', 'clients=localhost:5004'])

def _publish_chunk(sock, data):
	m = {
		'channel': 'audio',
		'formats': {
			'http-stream': {
				'content': data
			}
		}
	}
	sock.send(tnetstring.dumps(m), zmq.DONTWAIT)

def _input_worker():
	in_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	in_sock.bind(('127.0.0.1', 5004))

	out_sock = zmq_context.socket(zmq.PUSH)
	out_sock.connect('inproc://input')

	while True:
		data, addr = in_sock.recvfrom(65536)
		out_sock.send_multipart(['data', data])

def _publish_worker(cond):
	cond.acquire()

	in_sock = zmq_context.socket(zmq.PULL)
	in_sock.bind('inproc://input')

	cond.notify()
	cond.release()

	out_sock = zmq_context.socket(zmq.PUSH)
	out_sock.connect('tcp://localhost:5560')

	buf = ''
	packets = 0

	while True:
		msg = in_sock.recv_multipart()
		if msg[0] == 'data':
			buf += msg[1]
			packets += 1

		if (msg[0] == 'flush' and packets > 0) or packets >= 10:
			with r.pipeline() as pipe:
				pipe.multi()
				pipe.lpush('bufs', buf)
				pipe.ltrim('bufs', 0, 15)
				pipe.execute()

			_publish_chunk(out_sock, buf)
			buf = ''
			packets = 0

		if msg[0] == 'flush':
			r.delete('bufs')

class Command(BaseCommand):
	help = 'Background cleanup task'

	def add_arguments(self, parser):
		parser.add_argument('filename')

	def handle(self, *args, **options):
		cond = threading.Condition()
		cond.acquire()
		publish_thread = threading.Thread(target=_publish_worker, args=(cond,))
		publish_thread.daemon = True
		publish_thread.start()
		cond.wait()
		cond.release()

		input_thread = threading.Thread(target=_input_worker)
		input_thread.daemon = True
		input_thread.start()

		sock = zmq_context.socket(zmq.PUSH)
		sock.connect('inproc://input')

		r.delete('bufs')

		while True:
			_play(options['filename'])
			sock.send_multipart(['flush'])
			time.sleep(5)
