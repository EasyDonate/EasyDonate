from wsgiref.simple_server import make_server
from pyramid.paster import get_app
import os

application = get_app("%s/pyramid.ini" % os.path.dirname(os.path.realpath(__file__)), 'main')