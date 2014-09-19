#!/usr/bin/env python

import json, urlparse, sys, os, signal
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from subprocess import call

class GitAutoDeploy(BaseHTTPRequestHandler):

	CONFIG_FILEPATH = './GitAutoDeploy.conf.json'
	config = None
	quiet = False
	daemon = False

	@classmethod
	def getConfig(myClass):
		if(myClass.config == None):
			try:
				configString = open(myClass.CONFIG_FILEPATH).read()
			except:
				sys.exit('Could not load ' + myClass.CONFIG_FILEPATH + ' file')

			try:
				myClass.config = json.loads(configString)
			except:
				sys.exit(myClass.CONFIG_FILEPATH + ' file is not valid json')

			for repository in myClass.config['repositories']:
				if(not os.path.isdir(repository['path'])):
					sys.exit('Directory ' + repository['path'] + ' not found')
				if(not os.path.isdir(repository['path'] + '/.git')):
					sys.exit('Directory ' + repository['path'] + ' is not a Git repository')

		return myClass.config

	def do_POST(self):
		urls = self.parseRequest()
		for url in urls:
			paths = self.getMatchingPaths(url)
			for path in paths:
				self.pull(path)
				self.deploy(path)
		self.respond()

	def parseRequest(self):
		length = int(self.headers.getheader('content-length'))
		body = self.rfile.read(length)
		post = urlparse.parse_qs(body)
		items = []

		# If payload is missing, we assume gitlab syntax.
		if not 'payload' in post and 'repository' in body:
			response = json.loads(body)
			items.append(response['repository']['url'])

		# Otherwise, we assume github syntax.
		else:
			for itemString in post['payload']:
				item = json.loads(itemString)
				items.append(item['repository']['url'])

		return items

	def getMatchingPaths(self, repoUrl):
		res = []
		config = self.getConfig()
		for repository in config['repositories']:
			if(repository['url'] == repoUrl):
				res.append(repository['path'])
		return res

	def respond(self):
		self.send_response(200)
		self.send_header('Content-type', 'text/plain')
		self.end_headers()

	def pull(self, path):
		if(not self.quiet):
			print "\nPost push request received"
			print 'Updating ' + path
		call(['cd "' + path + '" && git fetch origin && git update-index --refresh &> /dev/null && git reset --hard origin/master'], shell=True)

	def deploy(self, path):
		config = self.getConfig()
		for repository in config['repositories']:
			if(repository['path'] == path):
				cmds = []
				if 'deploy' in repository:
					cmds.append(repository['deploy'])

				gd = config['global_deploy']
				print gd
				if len(gd[0]) is not 0:
					cmds.insert(0, gd[0])
				if len(gd[1]) is not 0:
					cmds.append(gd[1])

				if(not self.quiet):
					print 'Executing deploy command(s)'
				print cmds
				for cmd in cmds:
					call(['cd "' + path + '" && ' + cmd], shell=True)

				break


class GitAutoDeployMain:
	
	server = None

	def run(self):
		for arg in sys.argv:
			if(arg == '-d' or arg == '--daemon-mode'):
				GitAutoDeploy.daemon = True
				GitAutoDeploy.quiet = True
			if(arg == '-q' or arg == '--quiet'):
				GitAutoDeploy.quiet = True
		if(GitAutoDeploy.daemon):
			pid = os.fork()
			if(pid != 0):
				sys.exit()
			os.setsid()

		if(not GitAutoDeploy.quiet):
			print 'Github & Gitlab Autodeploy Service v 0.1 started'
		else:
			print 'Github & Gitlab Autodeploy Service v 0.1 started in daemon mode'

		self.server = HTTPServer(('', GitAutoDeploy.getConfig()['port']), GitAutoDeploy)
		self.server.serve_forever()

	def close(self, signum, frame):
		if(not GitAutoDeploy.quiet):
			print '\nGoodbye'

		if(self.server is not None):
			self.server.socket.close()
			sys.exit()

if __name__ == '__main__':
	gadm = GitAutoDeployMain()
	
	signal.signal(signal.SIGHUP, gadm.close)
	signal.signal(signal.SIGINT, gadm.close)

	gadm.run()