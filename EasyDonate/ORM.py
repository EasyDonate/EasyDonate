from sqlalchemy import Column, String, Integer, Float, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, validates, backref
import time, json

DecBase = declarative_base()

class Server(DecBase):
	__tablename__ = 'ezdonate_servers'
	
	id = Column(Integer, primary_key=True, autoincrement=True)
	name = Column(String(255))
	ip = Column(String(16))
	port = Column(Integer)
	
	@validates('port')
	def validate_port(self, key, port):
		assert port > 0
		assert port < 65535
		return port
	
	def __init__(self, name, ip, port, id=None):
		self.name = name
		self.ip = ip
		self.port = port
		self.id = id
	def __json__(self, request):
		return {'id': self.id, 'name': self.name, 'address': '{ip}:{port}'.format(ip=self.ip, port=self.port)}
		

class Subscriber(DecBase):
	__tablename__ = 'ezdonate_orders'
	
	id = Column(Integer, primary_key=True, autoincrement=True)
	serv_id = Column(Integer, ForeignKey('ezdonate_servers.id', ondelete='CASCADE'), nullable=False)
	server = relationship('Server', backref=backref('subs', cascade='all,delete', lazy='joined'))
	steamid = Column(String(32))
	item_id = Column(Integer, ForeignKey('ezdonate_items.id', ondelete='CASCADE'))
	item = relationship('Item', backref=backref('purchasers', cascade='all,delete', lazy='joined'))
	expires = Column(Integer)

	def __init__(self, serv_id, steamid, item_id, expires):
		self.serv_id = serv_id
		self.steamid = steamid
		self.item_id = item_id
		self.expires = expires
	def __json__(self, request):
		return {'id': self.id, 'server': self.serv_id, 'steamid': self.steamid, 'item': self.item_id, 'expires': self.expires}
	
class User(DecBase):
	__tablename__ = 'ezdonate_users'
	
	id = Column(Integer, primary_key=True, autoincrement=True)
	user = Column(String(64), unique=True)
	password = Column(String(512))
	email = Column(String(128), unique=True)
	name = Column(String(128))
	steam = Column(String(128))
	groups = Column(String(64))
	
	def __init__(self, user, password, email, groups):
		self.user = user
		self.password = password
		self.email = email
		self.groups = groups

class Item(DecBase):
	__tablename__ = 'ezdonate_items'
	
	id = Column(Integer, primary_key=True, autoincrement=True)
	group_id = Column(Integer, ForeignKey('ezdonate_itemgroups.id', ondelete='CASCADE'), nullable=False)
	group = relationship('ItemGroup', backref=backref('items', cascade='all, delete', lazy='joined'))
	name = Column(String(64))
	shortdesc = Column(String(256))
	description = Column(String(2048))
	price = Column(Float, nullable=False, default=0.0)
	duration = Column(Integer)
	arguments = Column(String(2048))
	
	def __init__(self, group_id, name, shortdesc, description, price, duration, arguments):
		self.group_id = group_id
		self.name = name
		self.shortdesc = shortdesc
		self.description = description
		self.price = price
		self.duration = duration
		self.arguments = arguments
	def __json__(self, request):
		return {'id': self.id, 'group': self.group_id, 'name': self.name, 'shortdesc': self.shortdesc, 'description': self.description, 
				'price': self.price, 'duration': self.duration, 'arguments': json.loads(self.arguments)}
		
class ItemGroup(DecBase):
	__tablename__ = 'ezdonate_itemgroups'
	
	id = Column(Integer, primary_key=True)
	name = Column(String(64))
	values = Column(String(2048))
	arguments = Column(String(2048))
	
	def __init__(self, name, values, arguments):	
		self.name = name
		self.arguments = arguments
		self.values = values
	def __json__(self, request):
		return {'id': self.id, 'name': self.name, 'fields': json.loads(self.values)}
		
class ServerItem(DecBase):
	__tablename__ = 'ezdonate_serveritems'
	
	item_id = Column(Integer, ForeignKey('ezdonate_items.id', ondelete='CASCADE'))
	item = relationship('Item', backref=backref('servitems', cascade='all,delete', lazy='joined'))
	serv_id = Column(Integer, ForeignKey('ezdonate_servers.id', ondelete='CASCADE'))
	server = relationship('Server', backref=backref('items', cascade='all,delete', lazy='joined'))
	__table_args__ = (PrimaryKeyConstraint('item_id', 'serv_id'), {})
	
	def __init__(self, item_id, serv_id):
		self.item_id = item_id
		self.serv_id = serv_id

class Transaction(DecBase):
	__tablename__ = 'ezdonate_transactions'
	
	txn_id = Column(Integer, primary_key=True, autoincrement=True)
	item_id = Column(Integer, ForeignKey('ezdonate_items.id'))
	item = relationship('Item')
	serv_id = Column(Integer, ForeignKey('ezdonate_servers.id'))
	server = relationship('Server')
	amount = Column(Float)
	steamid = Column(String(32))
	email = Column(String(128))
	time = Column(Integer)
	
	def __init__(self, item_id, serv_id, amount, steamid, email, time):
		self.item_id = item_id
		self.serv_id = serv_id
		self.amount = amount
		self.steamid = steamid
		self.email = email
		self.time = time
		
class OngoingTransaction(DecBase):
	__tablename__ = 'ezdonate_ongoingtxns'
	
	pay_id = Column(String(64), primary_key=True)
	txn_id = Column(Integer, ForeignKey('ezdonate_transactions.txn_id'))
	transaction = relationship('Transaction')
	
	def __init__(self, pay_id, txn_id):
		self.pay_id = pay_id
		self.txn_id = txn_id
		
class CompletedTransaction(DecBase):
	__tablename__ = 'ezdonate_completetxns'
	
	id = Column(Integer, primary_key=True, autoincrement=True)
	txn_id = Column(Integer)
	item_id = Column(Integer)
	serv_id = Column(Integer)
	steamid = Column(String(62))
	email = Column(String(128))
	amount = Column(Float)
	time_started = Column(Integer)
	time_finished = Column(Integer)
	
	def __init__(self, txn_id, item_id, serv_id, steamid, email, amount, time_started, time_finished=time.time()):
		self.txn_id = txn_id
		self.item_id = item_id
		self.serv_id = serv_id
		self.steamid = steamid
		self.email = email
		self.amount = amount
		self.time_started = time_started
		self.time_finished = time_finished

class Promotion(DecBase):
	__tablename__ = 'ezdonate_promotions'
	
	id = Column(Integer, primary_key=True, autoincrement=True)
	type = Column(Integer)
	value = Column(String(16))
	name = Column(String(64))
	code = Column(String(64))
	expires = Column(Integer)
	
	def __init__(self, type, value, name, code, expires):
		self.type = type
		self.value = value
		self.name = name
		self.code = code
		self.expires = expires
	def __json__(self, request):
		return {'id': self.id, 'type': self.type, 'value': self.value, 'name': self.name, 'code': self.code, 'expires': self.expires}
		
class ItemPromotion(DecBase):
	__tablename__ = 'ezdonage_promoitems'
	
	promo_id = Column(Integer, ForeignKey('ezdonate_promotions.id', ondelete='CASCADE'))
	promotion = relationship('Promotion', backref=backref('items', cascade='all,delete', lazy='joined'))
	item_id = Column(Integer, ForeignKey('ezdonate_items.id', ondelete='CASCADE'))
	item = relationship('Item', backref=backref('promotions', cascade='all,delete', lazy='joined'))
	__table_args__ = (PrimaryKeyConstraint('promo_id', 'item_id'), {})
	
	def __init__(self, promo_id, item_id):
		self.item_id = item_id
		self.promo_id = promo_id