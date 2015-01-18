#!/bin/env python

import os
import tornado.web
import tornado.httpserver
import tornado.ioloop
import tornado.options
import bcrypt
import motor
import tornado.gen
import bson

from tornado.options import define, options

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

define("port", default=8888, help="run on the given port", type=int)

class TemplateRendering:
	'''
	A simple class to hold method for rendering templete.
	'''
	def render_template(self, template_name, **kwargs):
		template_dirs = []
		if self.settings.get('template_path', ''):
			template_dirs.append(
					self.settings["template_path"])
		template_dirs.append(os.path.join(os.path.dirname(__file__), 'templates'))
		env = Environment(loader=FileSystemLoader(template_dirs))
		try:
			template = env.get_template(template_name)
		except TemplateNotFound:
			raise TemplateNotFound(template_name)
		content = template.render(kwargs)
		return content

class BaseHandler(tornado.web.RequestHandler, TemplateRendering):
	'''
	RequestHandler already has a `render()` method. I'm writing another
	method `render2()` and keeping the API almost same.
	'''
	def render2(self, template_name, **kwargs):
		'''
		This is for making some extra context variables available to
		the temple
		'''
		kwargs.update({
			'settings': self.settings,
			'static_url': self.settings.get('static_url_prefix', '/static'),
			'request': self.request,
			'xsrf_token': self.xsrf_token,
			'xsrf_form_html': self.xsrf_form_html,
			'title': self.settings['title'],
			})
		content = self.render_template(template_name, **kwargs)
		self.write(content)
        @property
        def db(self):
	  return self.application.db

class Application(tornado.web.Application):
  def __init__(self):
    handlers = [
        (r"/", HomeHandler),
        #(r"/login", LoginHandler),
        (r"/register", RegisterHandler),
        #(r"/logout", LogoutHandler),
        #(r"/testflash", TestFlashHandler),
        #(r"/test_auth", TestAuthHandler),
        #(r".*", PageNotFoundHandler),
    ]
    settings = dict(
        title = "tornado blog app",
        template_path=os.path.join(os.path.dirname(__file__), "templates"),
        static_path=os.path.join(os.path.dirname(__file__), "static"),
        xsrf_cookies=True,
        debug=True,
        login_url="/login",
        cookie_secret="4C2I8ieSSWyqJjs59dXlhLjosev9Ikxbvj3nxMZzxMI="
    )
    tornado.web.Application.__init__(self, handlers, **settings)
    # Have one global connection to the blog DB across all handlers
    self.db = motor.MotorClient().mblog

class HomeHandler(BaseHandler):
  @tornado.gen.coroutine
  def get(self):
    user_id = self.get_secure_cookie('bloguser')
    res = yield self.db.authors.find_one({"_id": bson.ObjectId(user_id)})
    print res
    name = ''
    if res:
      name = res['name']
    cursor = self.db.blogs.find()
    blog_list = yield cursor.to_list(length=5)
    self.render2('index.html', message=blog_list, bloguser=name)

  @tornado.gen.coroutine
  def post(self):
    name = self.get_argument('username')
    password = self.get_argument('password')
    cursor = self.db.authors.find({"name": name})
    while (yield cursor.fetch_next):
      user = cursor.next_object()
      print user
      try:
	if user['name'] == name:
	  if str(user['password']) == bcrypt.hashpw(password.encode('utf-8'), str(user['password'])):
	    self.set_secure_cookie('bloguser', str(user['_id']))
	    break;
      except Exception, e:
	print e
    self.redirect('/')

class RegisterHandler(BaseHandler):
  def get(self):
    self.render2("register.html")

  @tornado.gen.coroutine
  def post(self):
    id = self.get_argument("id", None)
    username=self.get_argument("username")
    password=self.get_argument("password")
    password_confirm = self.get_argument("confirm-password")
    print username, password

    # check user if it's in db
    cursor = self.db.authors.find({"name": username})
    while (yield cursor.fetch_next):
      user = cursor.next_object()
      print user
      try:
	# the while loop should be removed ?
        while True:
          print "find user: ", user['name']
          if user['name'] == username:
           self.redirect("/register")
           return
      except Exception, e:
        print e

    if password != password_confirm:
      self.redirect("/register")
      return
    self.write("user(%s) password(%s)register ok" %(username, password))
    password_digest = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12))
    # new user into db
    try:
      id = yield self.db.authors.insert({"name": username, "password": password_digest})
      print "insert: ", id, "|", str(id)
    except Exception, e:
      print e.message
      self.redirect("/register")
      return
    self.set_secure_cookie("bloguser", str(id))
    self.redirect(self.get_argument("next", "/"))

def main():
  tornado.options.parse_command_line()
  http_server = tornado.httpserver.HTTPServer(Application())
  http_server.listen(options.port)
  tornado.ioloop.IOLoop.instance().start()


if __name__ == '__main__':
  main()

