__version__ = "1.0.0+dev1744"
from pyramid.config import Configurator
from pyramid.view import view_config
from pyramid.events import NewRequest
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.renderers import JSON
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, scoped_session
from passlib.hash import pbkdf2_sha512
import paypalrestsdk
import ConfigParser, os, string, threading, certifi, random
from .ORM import DecBase, User

class Config():
	def __init__(self, configFile):
		self.parse = ConfigParser.SafeConfigParser({'community': 'EasyDonate', 'steam_key': None, 'api_key': None, 'read_only': False, 'elasticbeanstalk': False, 
													'auth_key': None})
		self.configFile = configFile
		self.parse.read(configFile)
		self.BeanStalk = self.parse.getboolean('app:main', 'elasticbeanstalk')
		if self.BeanStalk:
			self.DSN = 'mysql+pymysql://{0}:{1}@{2}:{3}/{4}'.format(os.environ['RDS_USERNAME'], os.environ['RDS_PASSWORD'],
																	os.environ['RDS_HOSTNAME'], os.environ['RDS_PORT'],
																	os.environ['RDS_DB_NAME'])
		else:
			self.DSN = self.parse.get('app:main', 'dsn', 0)
		self.Community = self.parse.get('app:main', 'community', 0)
		self.SteamAPI = self.parse.get('app:main', 'steam_key', 0)
		self.APIKey = self.parse.get('app:main', 'api_key', 0)
		self.AuthKey = self.parse.get('app:main', 'auth_key', 0)
		self.ReadOnly = self.parse.getboolean('app:main', 'read_only')
		if self.APIKey == 'None':
			self.APIKey = ''.join(random.choice(string.ascii_letters + string.digits) for x in range(32))
			self.parse.set('app:main', 'api_key', self.APIKey)
			config = open(self.configFile, 'w+')
			self.parse.write(config)
			config.close()
		if self.AuthKey == 'None':
			self.AuthKey = ''.join(random.choice(string.ascii_letters + string.digits + '-') for x in range(64))
			self.parse.set('app:main', 'auth_key', self.AuthKey)
			config = open(self.configFile, 'w+')
			self.parse.write(config)
			config.close()
		engine = create_engine(self.DSN)
		self.Session = scoped_session(sessionmaker(bind=engine))
		if self.ReadOnly:
			def ro_commit(*args, **kwargs):
				raise Exception('Database is in read-only mode')
				return
			self.Session.commit = ro_commit
		
		paypalrestsdk.configure({
			"mode": self.parse.get('app:paypal', 'mode', 0),
			"client_id": self.parse.get('app:paypal', 'client_id', 0),
			"client_secret": self.parse.get('app:paypal', 'client_secret', 0)}, ssl_options={'ca_certs': certifi.where()})
		DecBase.metadata.create_all(engine)
		users = self.Session.query(func.count(User.id)).scalar()
		if users == 0:
			self.Session.add(User('admin', pbkdf2_sha512.encrypt('ezdonate', rounds=16000, salt_size=32), 'admin@local.host', 'superadmin'))
			try:
				self.Session.commit()
			except:
				self.Session.rollback()

Settings = Config(os.path.join(os.path.dirname(__file__), 'Config', 'settings.ini'))

from .EDAuth import groups
import EDDaemon

def main(global_config, **settings):
	config = Configurator(settings=settings, root_factory='.EDModels.Donate')
	authn = AuthTktAuthenticationPolicy(secret=Settings.AuthKey, callback=groups, include_ip=True, hashalg='SHA512')
	config.include('pyramid_chameleon')
	config.set_authentication_policy(authn)
	config.set_authorization_policy(ACLAuthorizationPolicy())
	config.add_static_view('static', 'EasyDonate:static', cache_max_age=3600)
	config.add_renderer('prettyjson', JSON(indent=4))
	config.add_subscriber(new_request, NewRequest) #TODO: Make pretty
	
	config.add_route('home', '/')
	config.add_route('order', '/order/{server}/{product}')
	config.add_route('confirm', '/order/confirm')
	config.add_route('paypal/execute', '/paypal/execute/{txn}')
	config.add_route('paypal/cancel', '/paypal/cancel/{txn}')
	
	config.add_route('admin', '/admin')
	config.add_route('logout', '/logout')
	config.add_route('admin/users', '/admin/users')
	config.add_route('admin/servers', '/admin/servers')
	config.add_route('admin/account', '/admin/account')
	config.add_route('admin/password', '/admin/password')
	config.add_route('admin/products', '/admin/products')
	config.add_route('admin/config', '/admin/config')
	config.add_route('admin/promotions', '/admin/promotions')
	config.add_route('admin/orders', '/admin/orders')
	config.add_route('admin/products/groups', '/admin/products/groups')
	config.add_route('admin/products/servers', '/admin/products/servers/{server}')
	
	config.add_route('api', '/api/*traverse', factory='.EDAPI.API_Root')
	
	config.scan('.EDViews')

	thread = threading.Thread(target=EDDaemon.main)
	thread.daemon = True
	thread.start()
	return config.make_wsgi_app()
	
def SteamIDToCommunityID(steamid):
	steamid = steamid.lower()
	if not 'steam_' in steamid:
		raise SteamFormatException('SteamID Invalid', steamid)
	arr = steamid.split(':')
	try:
		communityid = int(arr[1]) + 76561197960265728 + (int(arr[2]) * 2)
	except:
		raise SteamFormatException('Error parsing SteamID', steamid)
	return communityid
	
def CommunityIDToSteamID(communityid):
	spart = (communityid - 76561197960265728) / 2.0
	if spart % 1 != 0:
		ipart = 1
	else:
		ipart = 0
	return "STEAM_0:{ipart}:{spart}".format(ipart=ipart, spart=int(spart))
	
def cleanup_session(request):
	Settings.Session.remove()

def new_request(newrequest):
	newrequest.request.add_finished_callback(cleanup_session)
	if 'csrf' in newrequest.request.cookies:
		newrequest.request.csrf = newrequest.request.cookies['csrf']
	else:
		newrequest.request.response.set_cookie('csrf', value=''.join(random.choice(string.ascii_letters + string.digits + '-_') for x in range(64)), max_age=1200)

def validateCSRF(request):
	return 'csrf_token' in request.POST and 'csrf' in request.cookies and request.POST['csrf_token'] == request.cookies['csrf']
		
class SteamFormatException(Exception):
	def __init__(self, message, steamid):
		self.message = message
		self.steamid = steamid
	
	def __str__(self):
		return "{message} SteamID: {steamid}".format(message=self.message, steamid=self.steamid)