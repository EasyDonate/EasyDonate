from pyramid.httpexceptions import HTTPNotFound, HTTPBadRequest, HTTPForbidden
from .ORM import User, Server, Item, ServerItem, Subscriber, ItemGroup, Promotion, ItemPromotion
from . import Settings
import inspect

class API_Root(object):
	def __getitem__(self, key):
		if key == 'IServers':
			return IServers()
		elif key == 'IItems':
			return IItems()
		elif key == 'ISubscribers':
			return ISubscribers()
		elif key == 'IEasyDonateAPI':
			return IEasyDonateAPI()
		else:
			raise KeyError

	def __init__(self, request):
		pass
		
class APIInterface(object):
	def __getitem__(self, key):
		if hasattr(self.__class__, key):
			obj = getattr(self.__class__, key)
			if inspect.isclass(obj):
				return obj()
		raise KeyError
	def __init__(self):
		pass
	def __json__(self, request):
		methods = []
		for name, obj in inspect.getmembers(self):
			if hasattr(obj, '_call'):
				methods.append(obj())
		return {'name': self.__class__.__name__, 'methods': methods}

class IServers(APIInterface):
	class GetServerList(object):
		def _call(self, request):
			servers = Settings.Session.query(Server).all()
			return {'severs': [server.id for server in servers]}
		def __init__(self):
			pass
		def __json__(self, request):
			return {'name': self.__class__.__name__, 'description': 'Retrieve a list of this communities game servers', 'parameters': []}
	class GetServerSummaries(object):
		def _call(self, request):
			if not 'servers' in request.GET:
				return HTTPBadRequest()
			getservers = request.GET['servers'].split(',')
			servers = Settings.Session.query(Server).filter(Server.id.in_(getservers)).all()
			if not servers:
				return HTTPBadRequest()
			return {'servers': servers}
		def __init__(self):
			pass
		def __json__(self, request):
			return {'name': self.__class__.__name__, 'description': 'Retrieve details of a serverid',
						'parameters': [
							{'name': 'servers', 'description': 'Comma-delimited of server IDs', 'optional': False, 'type': 'string'}
						]
					}
	class GetServerItems(object):
		def _call(self, request):
			if not 'sid' in request.GET:
				return HTTPBadRequest()
			server = Settings.Session.query(Server).filter(Server.id == request.GET['sid']).scalar()
			if not server:
				return HTTPBadRequest()
			items = [{"itemid": item.item.id, "groupid": item.item.group_id} for item in server.items]
			return {'item_count': len(items), 'items': items}
		def __init__(self):
			pass
		def __json__(self, request):
			return {'name': self.__class__.__name__, 'description': 'Retrieve list of items available on a server',
						'parameters': [
							{'name': 'sid', 'description': 'Server ID to look up', 'optional': False, 'type': 'int'}
						]
					}
	class GetServerSubs(object):
		def _call(self, request):
			if not 'sid' in request.GET:
				return HTTPBadRequest()
			server = Settings.Session.query(Server).filter(Server.id == request.GET['sid']).scalar()
			if not server:
				return HTTPBadRequest()
			subs = [{'subscriber': sub.id, 'item': sub.item_id} for sub in server.subs]
			return {'subscriber_count': len(subs), 'subscribers': subs}
		def __init__(self):
			pass
		def __json__(self, request):
			return {'name': self.__class__.__name__, 'description': 'Retrieve list of subscribers on a server',
						'parameters': [
							{'name': 'sid', 'description': 'Server ID to look up', 'optional': False, 'type': 'int'}
						]
					}
	pass
		
class IItems(APIInterface):
	class GetItemSummaries(object):
		def _call(self, request):
			if not 'items' in request.GET:
				return HTTPBadRequest()
			getitems = request.GET['items'].split(',')
			items = Settings.Session.query(Item).filter(Item.id.in_(getitems)).all()
			if not items:
				return HTTPBadRequest()
			return {'items': items}
		def __init__(self):
			pass
		def __json__(self, request):
			return {'name': self.__class__.__name__, 'description': 'Retrieve summaries of items',
						'parameters': [
							{'name': 'items', 'description': 'Comma-delimited of item IDs', 'optional': False, 'type': 'string'}
						]
					}
	class GetGroupSummaries(object):
		def _call(self, request):
			if not 'groups' in request.GET:
				return HTTPBadRequest()
			getgroups = request.GET['groups'].split(',')
			groups = Settings.Session.query(ItemGroup).filter(ItemGroup.id.in_(getgroups)).all()
			if not groups:
				return HTTPBadRequest()
			return {'groups': groups}
		def __init__(self):
			pass
		def __json__(self, request):
			return {'name': self.__class__.__name__, 'description': 'Retrieve summaries of item groups',
						'parameters': [
							{'name': 'groups', 'description': 'Comma-delimited of group IDs', 'optional': False, 'type': 'string'}
						]
					}
	class GetItemPromotions(object):
		def _call(self, request):
			if not 'item' in request.GET:
				return HTTPBadRequest()
			item = Settings.Session.query(Item).filter(Item.id == request.GET['item']).scalar()
			if not item:
				return HTTPBadRequest()
			return {'promotions': [promo.promotion for promo in item.promotions]}
		def __init__(self):
			pass
		def __json__(self, request):
			return {'name': self.__class__.__name__, 'description': 'Retrieve a list of promotions available for an item',
						'parameters': [
							{'name': 'item', 'description': 'Item ID to look up', 'optional': False, 'type': 'int'}
						]
					}
	pass
	
class ISubscribers(APIInterface):
	class GetSubscriberSummaries(object):
		def _call(self, request):
			if not 'subscribers' in request.GET:
				return HTTPBadRequest()
			getsubs = request.GET['subscribers'].split(',')
			subs = Settings.Session.query(Subscriber).filter(Subscriber.id.in_(getsubs)).all()
			if not subs:
				return HTTPBadRequest()
			return {'subscribers': subs}
		def __init__(self):
			pass
		def __json__(self, request):
			return {'name': self.__class__.__name__, 'description': 'Retrieve summaries of subscribers',
						'parameters': [
							{'name': 'subscribers', 'description': 'Comma-delimited of subscriber IDs', 'optional': False, 'type': 'string'}
						]
					}
	class SubscriberLookup(object):
		def _call(self, request):
			if not 'steamid' or not 'sid' in request.GET:
				return HTTPBadRequest()
			subs = Settings.Session.query(Subscriber).filter(Subscriber.steamid == request.GET['steamid'] and Subscriber.serv_id == request.GET['sid']).all()
			return {'subscribers': [{'id': sub.id, 'item': sub.item_id} for sub in subs]}
		def __init__(self):
			pass
		def __json__(self, request):
			return {'name': self.__class__.__name__, 'description': 'Searches for all subscribers with the matching steamid on a server',
						'parameters': [
							{'name': 'steamid', 'description': 'SteamID too look up', 'optional': False, 'type': 'string'},
							{'name': 'sid', 'description': 'Server ID of server to search', 'optional': False, 'type': 'int'}
						]
					}
	pass
	
class IEasyDonateAPI(APIInterface):
	class GetAPIInterfaces(object):
		def _call(self, request):
			return {'interfaces': [ISubscribers(), IItems(), IServers(), IEasyDonateAPI()]}
		def __init__(self):
			pass
		def __json__(self, request):
			return {'name': self.__class__.__name__, 'description': 'Lists all available API interfaces',
						'parameters': [
						]
					}
	pass