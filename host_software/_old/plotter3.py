#XXX: two separate *processes* for actlog vs audio; each with their own webserver

import matplotlib

# list of backends can be found under
# matplotlib.rcsetup.interactive_bk
# matplotlib.rcsetup.non_interactive_bk
# matplotlib.rcsetup.all_backends
#matplotlib.use('cairo.png')
matplotlib.use('Agg')

import collections
import time
import alsaaudio
import BaseHTTPServer
import cStringIO
import numpy as np
import usb.core

import matplotlib.pyplot as plt
import matplotlib.cm as cm

from matplotlib import colors
import matplotlib.backends.backend_agg
import threading





### activity log

actlog_buf_len = 120

# file name for HTTP address
fname_im_log = '/doppler_log.png'

fig_actlog = plt.figure(figsize=(10., 3.))
ax_actlog = fig_actlog.add_subplot(111)
ax_actlog.set_ylim(0, 65535)
ax_actlog.set_yticklabels([])
#im_actlog = ax_actlog.plot(actlog)[0]
im_actlog = ax_actlog.fill_between(range(actlog_buf_len), actlog_buf_len * [0], 0., color='0.8')

# create a memory-mapped image file
cstr_buf_actlog = cStringIO.StringIO()




class RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):

	def setup(self):
		BaseHTTPServer.BaseHTTPRequestHandler.setup(self)
		self.request.settimeout(60)



		'''	#plt.xticks(tick_locs, tick_labels, rotation=-30)
			plt.xlabel('time')
			plt.yticks([], [])
			# plot
			#for coll in (ax_actlog.collections):
			# save
			#lock_log_plot.acquire()
			cstr_buf_actlog.reset()
			cstr_buf_actlog.seek(0)
			fig_actlog.savefig(cstr_buf_actlog)
			#lock_log_plot.release()

			time.sleep(1.)'''

	def _fetch_actlog_data(self):
		# XXX grab audio data from the circular (FIFO?) buffer
		global logger_thread
		x = np.array(logger_thread.actlog_buf)
		print 'RequestHandler._fetch_actlog_data(): received ' + str(x.size) + ' samples'
		return x

	def _render_actlog_data(self, actlog_data):
		global fig_actlog, ax_actlog, im_actlog

		ax_actlog.collections.remove(im_actlog)
		im_actlog = ax_actlog.fill_between(np.linspace(actlog_data.size, 0., actlog_data.size), actlog_data, 0., color='0.8')
		#im_actlog.set_ydata(actlog)
		fig_actlog.canvas.draw()

	def _save_actlog_data(self):
		global fig_actlog, cstr_buf_actlog

		cstr_buf_actlog.reset()
		cstr_buf_actlog.seek(0)
		fig_actlog.savefig(cstr_buf_actlog, format='png')
		cstr_buf_actlog.seek(0)



	def do_GET(self):
		print 'RequestHandler.do_GET(): now serving HTTP request'
		t0 = time.time() * 1000. # [ms]
		if self.path[0:len(fname_im_log)] == fname_im_log:	# ignore GET values
			print("RequestHandler.do_GET(): request is HTTP GET of actlog image. Requester = " + str(self.client_address))

			global cstr_buf_actlog

			#time.sleep(0.1)
			x = self._fetch_actlog_data()
			t1 = time.time() * 1000. # [ms]
			print('RequestHandler.do_GET(): time elapsed after _fetch_actlog_data = ' + str(t1 - t0) + ' ms')
			self._render_actlog_data(x)
			t1 = time.time() * 1000. # [ms]
			print('RequestHandler.do_GET(): time elapsed after _render_actlog_data = ' + str(t1 - t0) + ' ms')
			self._save_actlog_data()
			t1 = time.time() * 1000. # [ms]
			print('RequestHandler.do_GET(): time elapsed after _save_actlog_data = ' + str(t1 - t0) + ' ms')

			data = cstr_buf_actlog.getvalue()

			#lock_actlog_plot.acquire()
			#cstr_buf_actlog.seek(0)
			self.send_response(200)
			self.send_header('Content-type', 'image/png')
			self.send_header('Content-length', len(data))
			self.send_header('Cache-control', 'no-store')
			self.end_headers()
			#self.wfile.write(cstr_buf_actlog.read())
			self.wfile.write(data)
			self.wfile.flush()
		else:
			self.send_error(404, 'File not found')

		t1 = time.time() * 1000. # [ms]
		print('RequestHandler.do_GET(): time elapsed = ' + str(t1 - t0) + ' ms')


class MyWebServer(threading.Thread):
	def run(self):
		print("MyWebServer.run(): Now starting HTTP server.")
		httpserver = BaseHTTPServer.HTTPServer(('', 8081), RequestHandler)
		httpserver.serve_forever()

	#def terminate(self):
	#	inp.close()


class MyLogger(threading.Thread):

	dev = None		# USB device
	actlog_buf = None

	def __init__(self, actlog_buf_len=2048):
		print('MyLogger.__init__(): initialising')

		threading.Thread.__init__(self)

		print '* Initialising buffer...'
		self.actlog_buf = collections.deque(maxlen=actlog_buf_len)
		self.actlog_buf.extend(actlog_buf_len * [0])

		self._open_device()

	def _open_device(self):
		print '* Opening logger connection...'
		self.dev = usb.core.find(idVendor=0x0483, idProduct=0x5726)

		if self.dev is None:
			raise Exception('Could not find device')


	def run(self):

		while True:
			try:
				print 'MyLogger.run(): Grabbing log value...'
				data = self.dev.ctrl_transfer(0xC0, 0x02, 0, 0, 2)
				data = data[0] + 256*data[1]
				print '  val = ' + str(data)
			
				self.actlog_buf.append(data)
				#actlog[:-1] = actlog[1:]
				#actlog[-1] = data
			
			except:
				self.dev = None
				try:
					self._open_device()
				except:
					pass

			time.sleep(1.)


# launch threads

global logger_thread
logger_thread = MyLogger(actlog_buf_len=actlog_buf_len)
logger_thread.start()

global webserver_thread
webserver_thread = MyWebServer()
#webserver_thread.run()
webserver_thread.setDaemon(True)
webserver_thread.start()

webserver_thread.join()	# wait until thread terminates (i.e. never)
