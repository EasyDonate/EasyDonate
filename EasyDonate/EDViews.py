from pyramid.view import view_config, forbidden_view_config
from pyramid.security import authenticated_userid, remember, forget, has_permission
from pyramid.httpexceptions import HTTPFound, HTTPNotFound, HTTPForbidden, HTTPBadRequest
from passlib.hash import pbkdf2_sha512 as password_hash
from .EDAuth import login
from .EDModels import Donate
from .ORM import User, Server, Item, ServerItem, Subscriber, ItemGroup, Promotion, ItemPromotion, Transaction, OngoingTransaction, CompletedTransaction
from . import Settings, Config, SteamIDToCommunityID, SteamFormatException, steamapi, validateCSRF
import json, time, paypalrestsdk, datetime, re, random, string, certifi

@view_config(route_name='home', renderer='templates/home.pt')
def home(request):
	servers = list()
	products = list()
	for row in Settings.Session.query(Server).all():
		servers.append(row)
	if 'sid' in request.params:
		try:
			here = int(request.params['sid'])
		except:
			here = None
		for row in Settings.Session.query(ServerItem).filter(ServerItem.serv_id == request.params['sid']):
			products.append(row.item)
	else:
		here = None
	
	return {"community": Settings.Community, "servers": servers, "products": products, 'here': here}

@view_config(route_name='order', renderer='templates/order.pt')
def order(request): 
	server = Settings.Session.query(Server).filter(Server.id == request.matchdict['server']).scalar()
	item = Settings.Session.query(Item).filter(Item.id == request.matchdict['product']).scalar()
	path = [{"href": request.route_url('home'), "name": "Home", "active": False}, 
			{"href": '{href}?sid={sid}'.format(href=request.route_url('home'), sid=server.id), "name": server.name, "active": False},
			{"href": request.route_url('order', server=server.id, product=item.id), "name": item.name, "active": True}]
	errors = []
	if not server or not item or not item in [servitem.item for servitem in server.items]:
		return HTTPFound(location=request.route_url('home'))
	price = item.price
	for promotion in [promo.promotion for promo in item.promotions if promo.promotion.type == 1 and '%' not in promo.promotion.value and time.time() < promo.promotion.expires]:
		try:
			price = price - float(promotion.value)
		except:
			continue
	for promotion in [promo.promotion for promo in item.promotions if promo.promotion.type == 1 and '%' in promo.promotion.value and time.time() < promo.promotion.expires]:
		try:
			price = price - (price * (float(promotion.value.replace('%', '')) / 100))
		except:
			continue;
	if price < 0:
		price = 0
	if 'form.submitted' in request.params:
		try:
			steamid = SteamIDToCommunityID(request.params['input.steamid'])
		except SteamFormatException:
			errors.append('steamid')
		if not re.match(r'[^@]+@[^@]+\.[^@]+', request.params['input.email']):
			errors.append('email')
		if request.params['input.code'].strip():
			print "Code: %s" % request.params['input.code']
			code = None
			for promotion in [promo.promotion for promo in item.promotions if promo.promotion.type == 2 and time.time() < promo.promotion.expires]:
				if promotion.code == request.params['input.code']:
					code = promotion
					break
			if not code:
				errors.append('promo')
		if not errors:
			order = {'steamid': request.params['input.steamid'], 'email': request.params['input.email'], 
					'promocode': request.params['input.code'], 'server': server.id, 'item': item.id}
			response = HTTPFound(location=request.route_url('confirm'))
			response.set_cookie('order', value=json.dumps(order), max_age=300)
			return response

	path = [{"href": request.route_url('home'), "name": "Home", "active": False}, 
			{"href": '{href}?sid={sid}'.format(href=request.route_url('home'), sid=server.id), "name": server.name, "active": False},
			{"href": request.route_url('order', server=server.id, product=item.id), "name": item.name, "active": True}]
	return {'community': Settings.Community, 'item': item, 'server': server, 'path': path, 'errors': errors, 'price': round(price,2), 'path': path}
	
@view_config(route_name='confirm', renderer='templates/confirm.pt')
def confirm(request):
	if not 'order' in request.cookies:
		return {'error': True, 'community': Settings.Community}
	order = json.loads(request.cookies['order'])
	try:
		steamid = order['steamid']
		email = order['email']
		promocode = order['promocode']
		server = order['server']
		item = order['item']
		promo = None
	except:
		return {'error': True, 'community': Settings.Community}
	server = Settings.Session.query(Server).filter(Server.id == order['server']).scalar()
	item = Settings.Session.query(Item).filter(Item.id == order['item']).scalar()
	if not server or not item or not re.match(r'[^@]+@[^@]+\.[^@]+', email):
		return {'error': True, 'community': Settings.Community}
	promotions = []
	price = item.price
	for promotion in [promo.promotion for promo in item.promotions if promo.promotion.type == 1 and '%' not in promo.promotion.value and time.time() < promo.promotion.expires]:
		try:
			price = price - float(promotion.value)
			promotions.append(promotion)
		except:
			continue
	for promotion in [promo.promotion for promo in item.promotions if promo.promotion.type == 1 and '%' in promo.promotion.value and time.time() < promo.promotion.expires]:
		try:
			price = price - (price * (float(promotion.value.replace('%', '')) / 100))
			promotions.append(promotion)
		except:
			continue;
	if price < 0:
		price = 0
	try:
		commid = SteamIDToCommunityID(steamid)
	except SteamFormatException:
		return {'error': True, 'community': Settings.Community}
	if promocode != '':
		print "Code: %s" % promocode
		for promotion in [promo.promotion for promo in item.promotions if promo.promotion.type == 2 and time.time() < promo.promotion.expires]:
			if promotion.code == promocode:
				promo = promotion
				if '%' in promo.value:
					try:
						price = price - (price * (float(promo.value.replace('%', '')) / 100))
						promotions.append(promo)
					except:
						pass
				else:
					try:
						price = price - float(promo.value)
						promotions.append(promo)
					except:
						pass
				break
	if price < 0:
		price = 0
	if 'checkout' in request.params:
		txn = Transaction(item.id, server.id, round(price,2), steamid, email, time.time())
		Settings.Session.add(txn)
		Settings.Session.flush()
		Settings.Session.refresh(txn)
		payment = paypalrestsdk.Payment({
			"intent": "sale",
			"payer": {"payment_method": "paypal"},
			"redirect_urls": {
				"return_url": request.route_url('paypal/execute', txn=txn.txn_id),
				"cancel_url": request.route_url('paypal/cancel', txn=txn.txn_id)},
			"transactions": [{
				"item_list": {
					"items": [{
						"name": item.name,
						"sku": item.id,
						"price": round(price,2) if round(price,2) % 1 != 0 else int(round(price,2)),
						"currency": "USD",
						"quantity": 1 }]},
				"amount": {
					"total": round(price,2) if round(price,2) % 1 != 0 else int(round(price,2)),
					"currency": "USD",}}]})
		if payment.create():
			Settings.Session.add(OngoingTransaction(payment.id, txn.txn_id))
			try:
				Settings.Session.commit()
			except:
				Settings.Session.rollback()
			for link in payment.links:
				if link.method == 'REDIRECT':
					redirect_url = link.href
			response = HTTPFound(location=redirect_url)
			response.delete_cookie('order')
			return response
		else:
			print payment.error
			Settings.Session.delete(txn)
			try:
				Settings.Session.commit()
			except:
				Settings.Session.rollback()
			return {'error': True, 'community': Settings.Community}
	steamapi.core.APIConnection(api_key=Settings.SteamAPI)
	user = steamapi.user.SteamUser(commid)
	path = [{"href": request.route_url('home'), "name": "Home", "active": False}, 
			{"href": '{href}?sid={sid}'.format(href=request.route_url('home'), sid=server.id), "name": server.name, "active": False},
			{"href": request.route_url('order', server=server.id, product=item.id), "name": item.name, "active": True}]
	return {'item': item, 'server': server, 'user': user, 'email': email, 'steamid': steamid, 'promotions': promotions, 'error': False, 'path': path, 
			'price': round(price,2), 'community': Settings.Community}
			
@view_config(route_name='paypal/execute', renderer='templates/execute.pt')
def execute(request):
	if not 'txn' in request.matchdict or not 'PayerID' in request.params:
		return {'community': Settings.Community, 'error': True}
	txn = Settings.Session.query(OngoingTransaction).filter(OngoingTransaction.txn_id == request.matchdict['txn']).scalar()
	if not txn:
		return {'community': Settings.Community, 'error': True}
	payment = paypalrestsdk.Payment.find(txn.pay_id)
	if not payment.execute({'payer_id': request.params['PayerID']}):
		return {'community': Settings.Community, 'error': True}
	Settings.Session.add(CompletedTransaction(txn.txn_id, txn.transaction.item_id, txn.transaction.serv_id, txn.transaction.steamid, txn.transaction.email, txn.transaction.amount, txn.transaction.time))
	Settings.Session.add(Subscriber(txn.transaction.serv_id, txn.transaction.steamid, txn.transaction.item_id, ((time.time() + (txn.transaction.item.duration * 86400)) if txn.transaction.item.duration > 0 else -1)))
	Settings.Session.delete(txn.transaction)
	Settings.Session.delete(txn)
	try:
		Settings.Session.commit()
	except:
		Settings.Session.rollback()
	return {'community': Settings.Community, 'error': False}

@view_config(route_name='paypal/cancel', renderer='templates/cancel.pt')
def cancel(request):
	txn = Settings.Session.query(OngoingTransaction).filter(OngoingTransaction.txn_id == request.matchdict['txn']).scalar()
	if not txn:
		return {'community': Settings.Community, 'error': True}
	Settings.Session.delete(txn.transaction)
	Settings.Session.delete(txn)
	try:
		Settings.Session.commit()
	except:
		Settings.Session.rollback()
		return {'community': Settings.Community, 'error': True}
	return {'community': Settings.Community, 'error': False}
	
	
#=============================================#
#=====================API=====================#	
@view_config(route_name='api', renderer='prettyjson')
def api(request):
	if request.matchdict['interface'] == 'IServers':
		if not 'key' in request.GET or request.GET['key'] != Settings.APIKey:
			return HTTPForbidden()
		if request.matchdict['method'] == 'GetServerList':
			servers = Settings.Session.query(Server).all()
			return {'severs': [server.id for server in servers]}
		elif request.matchdict['method'] == 'GetServerSummaries':
			if not 'servers' in request.GET:
				return HTTPBadRequest()
			getservers = request.GET['servers'].split(',')
			servers = Settings.Session.query(Server).filter(Server.id.in_(getservers)).all()
			if not servers:
				return HTTPBadRequest()
			return {'servers': servers}
		elif request.matchdict['method'] == 'GetServerItems':
			if not 'sid' in request.GET:
				return HTTPBadRequest()
			server = Settings.Session.query(Server).filter(Server.id == request.GET['sid']).scalar()
			if not server:
				return HTTPBadRequest()
			items = [{"itemid": item.item.id, "groupid": item.item.group_id} for item in server.items]
			return {'item_count': len(items), 'items': items}
		elif request.matchdict['method'] == 'GetServerSubs':
			if not 'sid' in request.GET:
				return HTTPBadRequest()
			server = Settings.Session.query(Server).filter(Server.id == request.GET['sid']).scalar()
			if not server:
				return HTTPBadRequest()
			subs = [{'subscriber': sub.id, 'item': sub.item_id} for sub in server.subs]
			return {'subscriber_count': len(subs), 'subscribers': subs}
	elif request.matchdict['interface'] == 'IItems':
		if not 'key' in request.GET or request.GET['key'] != Settings.APIKey:
			return HTTPForbidden()
		if request.matchdict['method'] == 'GetItemDetails':
			if not 'items' in request.GET:
				return HTTPBadRequest()
			getitems = request.GET['items'].split(',')
			items = Settings.Session.query(Item).filter(Item.id.in_(getitems)).all()
			if not items:
				return HTTPBadRequest()
			return {'items': items}
		elif request.matchdict['method'] == 'GetGroupDetails':
			if not 'groups' in request.GET:
				return HTTPBadRequest()
			getgroups = request.GET['groups'].split(',')
			groups = Settings.Session.query(ItemGroup).filter(ItemGroup.id.in_(getgroups)).all()
			if not groups:
				return HTTPBadRequest()
			return {'groups': groups}
		elif request.matchdict['method'] == 'GetItemPromotions':
			if not 'item' in request.GET:
				return HTTPBadRequest()
			item = Settings.Session.query(Item).filter(Item.id == request.GET['item']).scalar()
			if not item:
				return HTTPBadRequest()
			return {'promotions': [promo.promotion for promo in item.promotions]}
	elif request.matchdict['interface'] == 'ISubscribers':
		if not 'key' in request.GET or request.GET['key'] != Settings.APIKey:
			return HTTPForbidden()
		if request.matchdict['method'] == 'GetSubscriberSummaries':
			if not 'subscribers' in request.GET:
				return HTTPBadRequest()
			getsubs = request.GET['subscribers'].split(',')
			subs = Settings.Session.query(Subscriber).filter(Subscriber.id.in_(getsubs)).all()
			if not subs:
				return HTTPBadRequest()
			return {'subscribers': subs}
		elif request.matchdict['method'] == 'SubscriberLookup':
			if not 'steamid' or not 'sid' in request.GET:
				return HTTPBadRequest()
			subs = Settings.Session.query(Subscriber).filter(Subscriber.steamid == request.GET['steamid'] and Subscriber.serv_id == request.GET['sid']).all()
			return {'subscribers': [{'id': sub.id, 'item': sub.item_id} for sub in subs]}
	return HTTPNotFound()
	
#=============================================#
#===============Admin & Login=================#
@forbidden_view_config(renderer='templates/login.pt')
def view_login(request):
	user = ''
	result = ''
	if 'login.submitted' in request.params:
		user = request.params['login']
		if login(user, request.params['password']):
			headers = remember(request, user)
			
			return HTTPFound(location = request.route_url('admin'), headers = headers)
		result = 'Login Failed'
	
	return {'message': result, 'url': request.route_url('admin'), 'login': user, "community": Settings.Community}
	
@view_config(route_name='logout')
def logout(request):
	headers = forget(request)
	return HTTPFound(location = request.route_url('admin'), headers = headers)
	
@view_config(route_name='admin', renderer='templates/admin/admin.pt', permission='admin')
def admin(request):
	if(has_permission('root', Donate, request)):
		permission = 'root'
	else:
		permission = 'admin'
	servers = Settings.Session.query(Server).all()
	orders = Settings.Session.query(Subscriber).all()
	products = Settings.Session.query(Item).all()
	promotions = Settings.Session.query(Promotion).all()
	
	path = [{'name': 'Home', 'url': request.route_url('admin')}]
	return {'community': Settings.Community,  'path': path, 'permission': permission, 'settings': Settings, 
			'info': {'servers': servers, 'orders': orders, 'products': products, 'promotions': promotions}}
	
@view_config(route_name='admin/servers', renderer='templates/admin/servers.pt', permission='admin')
def servers(request):
	if(has_permission('root', Donate, request)):
		permission = 'root'
	else:
		permission = 'admin'

	path = [{'name': 'Home', 'url': request.route_url('admin')}, {'name': 'Servers', 'url': request.route_url('admin/servers')}]

	servers = Settings.Session.query(Server).all()

	error = None
	action = None
	server = None
	if 'del' in request.params and validateCSRF(request):
		try:
			id = int(request.params['del'])
			if id != -1:
				for row in Settings.Session.query(Server).filter(Server.id == request.params['del']):
					Settings.Session.delete(row)
					servers.remove(row)
				try:
					Settings.Session.commit()
				except:
					Settings.Session.rollback()
		except:
			error = 'Invalid Server ID'
	if 'add.server.submitted' in request.params:
		try:
			port = int(request.params['server.port'])
		except ValueError:
			port = -1
		if port < 0 or port > 65535:
			error = 'Port is invalid'
		if not error:
			if Settings.Session.query(Server).filter(Server.name == request.params['server.name']).count() == 0:
				server = Server(request.params['server.name'], request.params['server.addr'], int(request.params['server.port']))
				Settings.Session.add(server)
				try:
					Settings.Session.commit()
				except:
					Settings.Session.rollback()
					error = "Couldn't create server"
				servers.append(server)
			else:
				error = "Server already exists"
	if 'addserver' in request.params:
		action = 'addserver'
	elif 'manage' in request.params:
		server = Settings.Session.query(Server).filter(Server.id == request.params['manage']).scalar()
		if server:
			action = 'manage'
	elif 'manage.server.submitted' in request.params:
		server = Settings.Session.query(Server).filter(Server.id == request.params['server.id']).scalar()
		if server:
			Settings.Session.query(Server).filter(Server.id == server.id).update({'name': request.params['server.name'], 'ip': request.params['server.addr'], 'port': request.params['server.port']})
			try:
				Settings.Session.commit()
			except:
				Settings.Session.rollback()
	
	return {'community': Settings.Community,  'servers': servers, 'error': error, 'path': path, 'permission': permission,
			'action': action, 'server': server}
	
@view_config(route_name='admin/users', renderer='templates/admin/users.pt', permission='admin')
def users(request):
	path = [{'name': 'Home', 'url': request.route_url('admin')}, {'name': 'Users', 'url': request.route_url('admin/users')}]
	
	if(has_permission('root', Donate, request)):
		permission = 'root'
	else:
		permission = 'admin'
	
	error = None
	if 'del' in request.params and validateCSRF(request):
		if permission != 'root':
			error = 'You do not have permission to remove users'
		user = Settings.Session.query(User).filter(User.id == request.params['del']).scalar()
		if not user:
			error = 'Invalid user specified'
		if user and user.user == authenticated_userid(request):
			error = 'You can not delete yourself'
		if not error:
			Settings.Session.delete(user)
			try:
				Settings.Session.commit()
			except:
				Settings.Session.rollback()
				error = 'There was an error removing the user'
	if 'form.submitted' in request.params and validateCSRF(request):
		if request.params['password'] != request.params['repeatpass']:
			error = 'Passwords entered do not match'
		if request.params['usergroup'] == 'superadmin' and not permission == 'root':
			error = 'Request invalid'
		if Settings.Session.query(User).filter(User.name == request.params['username']).count() > 0:
			error = 'User already exists'
		if not error:
			user = User(request.params['username'], password_hash.encrypt(request.params['password'], rounds=16000, salt_size=32), None, request.params['usergroup'])
			Settings.Session.add(user)
			try:
				Settings.Session.commit()
			except:
				Settings.Session.rollback()
				error = 'There was an error adding the user'
	
	users = list()
	if 'offset' in request.params:
		offset = request.params['offset']
	else:
		offset = 0
	for user in Settings.Session.query(User).offset(offset):
		users.append(user)
	
	return {'permission': permission, 'community': Settings.Community,  'users': users, 'path': path, 'error': error}
	
@view_config(route_name='admin/account', renderer='templates/admin/account.pt', permission='admin')
def manageAccount(request):
	if(has_permission('root', Donate, request)):
		permission = 'root'
	else:
		permission = 'admin'

	path = [{'name': 'Home', 'url': request.route_url('admin')},{'name': 'Account Management', 'url': request.route_url('admin/account')}]
	user = Settings.Session.query(User).filter(User.user == authenticated_userid(request)).scalar()
	error = None
	if 'form.submitted' in request.params:
		user.email = request.params['email']
		user.steam = request.params['steam']
		user.name = request.params['name']
		Settings.Session.query(User).filter(User.id == user.id).update({'name': user.name, 'steam': user.steam, 'email': user.email})
		try:
			Settings.Session.commit()
		except:
			Settings.Session.rollback()
			error = 'There was an error applying changes'
	if not user:
		
		return HTTPFound(location=request.route_url('login'))
	
	return {'community': Settings.Community,  'path': path, 'user': user, 'error': error, 'permission': permission}
	
@view_config(route_name='admin/password', renderer='templates/admin/password.pt', permission='admin')
def passwordChange(request):
	if(has_permission('root', Donate, request)):
		permission = 'root'
	else:
		permission = 'admin'
	user = Settings.Session.query(User).filter(User.user == authenticated_userid(request)).scalar()
	error = None
	if 'form.submitted' in request.params:
		if not password_hash.verify(request.params['curpass'], user.password):
			error = 'Current password is incorrect'
		if request.params['newpass'] != request.params['repeatnew']:
			error = 'Passwords do not match'
		if not error:
			password = password_hash.encrypt(request.params['newpass'], rounds=16000, salt_size=32)
			Settings.Session.query(User).filter(User.id == user.id).update({'password': password})
			try:
				Settings.Session.commit()
			except:
				Settings.Session.rollback()
				error = 'There was an error applying changes'
	path = [{'name': 'Home', 'url': request.route_url('admin')},{'name': 'Account Management', 'url': request.route_url('admin/account')},
			{'name': 'Change Password', 'url': request.route_url('admin/password')}]
	
	return {'community': Settings.Community,  'path': path, 'permission': permission, 'error': error}
	
@view_config(route_name='admin/products/groups', renderer='templates/admin/productgroups.pt', permission='admin')
def manageGroups(request):
	path = [{'name': 'Home', 'url': request.route_url('admin')},{'name': 'Products', 'url': request.route_url('admin/products')},
			{'name': 'Groups', 'url': request.route_url('admin/products/groups')}]
	if(has_permission('root', Donate, request)):
		permission = 'root'
	else:
		permission = 'admin'
	action = None
	groups = None
	error = None
	group = None
	if 'manage' in request.params:
		action = 'manage'
		group = Settings.Session.query(ItemGroup).filter(ItemGroup.id == request.params['manage']).scalar()
	elif 'del' in request.params and validateCSRF(request):
		rem = Settings.Session.query(ItemGroup).filter(ItemGroup.id == request.params['del']).scalar()
		if rem:
			Settings.Session.delete(rem)
		try:
			Settings.Session.commit()
		except:
			Settings.Session.rollback()
			error = "There was an error deleting the group"
	elif 'new.group' in request.params:
		action = 'newgroup'
	elif 'newgroup.form.submitted' in request.params:
		fields = list()
		for k in request.params:
			if 'fname' in k:
				fields.append(request.params[k])
		Settings.Session.add(ItemGroup(request.params['groupname'], json.dumps(fields), None))
		try:
			Settings.Session.commit()
		except:
			Settings.Session.rollback()
			error = "There was an error adding the group"
	elif 'savegroup.form.submitted' in request.params:
		fields = list()
		for k in request.params:
			if 'fname' in k:
				fields.append(request.params[k])
		Settings.Session.query(ItemGroup).filter(ItemGroup.id == request.params['groupid']).update({'values': json.dumps(fields)})
		try:
			Settings.Session.commit()
		except:
			Settings.Session.rollback()
			error = "There was an error updating the group"
	if not action:
		return HTTPFound(location=request.route_url('admin/products'))
	
	return {'community': Settings.Community,  'path': path, 'permission': permission,
			'groups': groups, 'action': action, 'group': group}
			
@view_config(route_name='admin/products', renderer='templates/admin/manageproducts.pt', permission='admin')
def manageProducts(request):
	path = [{'name': 'Home', 'url': request.route_url('admin')},{'name': 'Products', 'url': request.route_url('admin/products')}]
	if(has_permission('root', Donate, request)):
		permission = 'root'
	else:
		permission = 'admin'
	action = None
	group = None
	groups = None
	item = None
	if 'add' in request.params:
		group = Settings.Session.query(ItemGroup).filter(ItemGroup.id == request.params['add']).scalar()
		if group:
			action = {'action': 'add'}
	if 'product.save' in request.params and validateCSRF(request):
		arguments = list()
		for k in request.params:
			if 'product.' in k or 'csrf' in k:
				continue
			else:
				arguments.append({k: request.params[k]})
		Settings.Session.add(Item(request.params['product.gid'], request.params['product.name'], 
									request.params['product.shortdesc'], request.params['product.longdesc'], 
									request.params['product.price'], request.params['product.duration'], json.dumps(arguments)))
		try:
			Settings.Session.commit()
		except:
			Settings.Session.rollback()
			error = 'There was an error saving the product'
	if 'del' in request.params and validateCSRF(request):
		item = Settings.Session.query(Item).filter(Item.id == request.params['del']).scalar()
		if item:
			Settings.Session.delete(item)
			try:
				Settings.Session.commit()
			except:
				Settings.Session.rollback()
	if 'manage' in request.params:
		item = Settings.Session.query(Item).filter(Item.id == request.params['manage']).scalar()
		if item:
			action = {'action': 'manage'}
	if 'save.submitted' in request.params and validateCSRF(request):
		item = Settings.Session.query(Item).filter(Item.id == request.params['product.id']).scalar()
		if item:
			item.name = request.params['product.name']
			item.price = request.params['product.price']
			item.duration = request.params['product.duration']
			item.shortdesc = request.params['product.shortdesc']
			item.description = request.params['product.longdesc']
			arguments = list()
			for k in request.params:
				if not 'product.' in k and not 'csrf' in k:
					arguments.append({k: request.params[k]})
			item.arguments = json.dumps(arguments)
			Settings.Session.query(Item).filter(Item.id == item.id).update({'name': item.name, 'price': item.price, 'duration': item.duration, 'shortdesc': item.shortdesc, 'description': item.description})
			try:
				Settings.Session.commit()
			except:
				Settings.Session.rollback()
	if 'promotions.submitted' in request.params:
		Settings.Session.query(ItemPromotion).filter(ItemPromotion.item_id == request.params['item.id']).delete()
		for k in request.params:
			if not 'promo-' in k:
				continue
			promo = k.replace('promo-', '')
			print promo
			Settings.Session.add(ItemPromotion(promo, request.params['item.id']))
		try:
			Settings.Session.commit()
		except:
			Settings.Session.rollback()
	if 'promotions' in request.params:
		item = Settings.Session.query(Item).filter(Item.id == request.params['promotions']).scalar()
		if item:
			promogroups = [{'name': 'Sale', 'id': 1, 'requires_code': False}, {'name': 'Promo Code', 'id': 2, 'requires_code': True}]
			for group in promogroups:
				promotions = []
				for row in Settings.Session.query(Promotion).filter(Promotion.type == group['id']):
					promotions.append(row)
				group['promotions'] = promotions
			action = {'action': 'promotions', 'item': item, 'promogroups': promogroups}
	
	if not action:
		groups = list()
		for group in Settings.Session.query(ItemGroup).all():
			groups.append(group)
	
	return {'community': Settings.Community,  'path': path, 'permission': permission,
			'action': action, 'group': group, 'groups': groups, 'item': item}
			
@view_config(route_name='admin/products/servers', renderer='templates/admin/serverproducts.pt', permission='admin')
def serverProducts(request):
	path = [{'name': 'Home', 'url': request.route_url('admin')},{'name': 'Products', 'url': request.route_url('admin/products')}]
	if(has_permission('root', Donate, request)):
		permission = 'root'
	else:
		permission = 'admin'
	
	server = Settings.Session.query(Server).filter(Server.id == request.matchdict['server']).scalar()
	if not server:
		
		return HTTPFound(location=request.route_url('admin/products'))

	path.append({'name': 'Server Products: ' + str(server.id), 'url': request.route_url('admin/products/servers', server=server.id)})
	
	action = None
	groups = None
	if 'add' in request.params:
		action = 'addproducts'
		groups = list()
		for group in Settings.Session.query(ItemGroup).all():
			groups.append(group)
	if 'save.newproducts' in request.params:
		for k in request.params:
			if 'add-' in k:
				item = Settings.Session.query(Item).filter(Item.id == request.params[k]).scalar()
				if item:
					Settings.Session.add(ServerItem(item.id, server.id));
		try:
			Settings.Session.commit()
		except:
			Settings.Session.rollback()
	if 'delete.selected' in request.params:
		for k in request.params:
			if 'delete-' in k:
				Settings.Session.query(ServerItem).filter(ServerItem.item_id == request.params[k], ServerItem.serv_id == server.id).delete()
		try:
			Settings.Session.commit()
		except:
			Settings.Session.rollback()
	
	return {'community': Settings.Community, 'path': path, 'permission': permission,
			'server': server, 'action': action, 'groups': groups}
@view_config(route_name='admin/config', renderer='templates/admin/config.pt', permission='root')
def configView(request):
	if(has_permission('root', Donate, request)):
		permission = 'root'
	else:
		permission = 'admin'

	if 'form.submitted' in request.params and validateCSRF(request):
		if request.params['config.community'] != Settings.Community:
			Settings.parse.set('app:main', 'community', request.params['config.community'])
			Settings.Community = request.params['config.community']
		if request.params['config.steamkey'] != Settings.SteamAPI:
			Settings.parse.set('app:main', 'steam_key', request.params['config.steamkey'])
			Settings.SteamAPI = request.params['config.steamkey']
		if 'config.regenerate' in request.params:
			Settings.APIKey = ''.join(random.choice(string.ascii_letters + string.digits) for x in range(32))
			Settings.parse.set('app:main', 'api_key', Settings.APIKey)
		if request.params['paypal.client_id'] != Settings.parse.get('app:paypal', 'client_id', 0):
			Settings.parse.set('app:paypal', 'client_id', request.params['paypal.client_id'])
			Settings.parse.set('app:paypal', 'client_secret', request.params['paypal.secret'])
		if request.params['paypal.mode'] != Settings.parse.get('app:paypal', 'mode', 0):
			Settings.parse.set('app:paypal', 'mode', request.params['paypal.mode'])
		config = open(Settings.configFile, 'w+')
		Settings.parse.write(config)
		config.close()
		paypalrestsdk.configure({
			"mode": Settings.parse.get('app:paypal', 'mode', 0),
			"client_id": Settings.parse.get('app:paypal', 'client_id', 0),
			"client_secret": Settings.parse.get('app:paypal', 'client_secret', 0)}, ssl_options={'ca_certs': certifi.where()})	
		
	path = [{'name': 'Home', 'url': request.route_url('admin')}, {'name': 'Configuration', 'url': request.route_url('admin/config')}]
	
	return {'community': Settings.Community,  'path': path, 'permission': permission, 'settings': Settings}
	
@view_config(route_name='admin/promotions', renderer='templates/admin/promotions.pt', permission='admin')
def viewPromotions(request):
	if(has_permission('root', Donate, request)):
		permission = 'root'
	else:
		permission = 'admin'
		
	action = None
	groups = [{'name': 'Sale', 'id': 1, 'requires_code': False}, {'name': 'Promo Code', 'id': 2, 'requires_code': True}]
	if 'add' in request.params:
		try:
			id = int(request.params['add'])
		except:
			id = None
		if id in [group['id'] for group in groups]:
			action = {'action': 'add', 'group': groups[id - 1]}
	elif 'save.submitted' in request.params and validateCSRF(request):
		try:
			id = int(request.params['group.id'])
		except:
			id = None
		if id in [group['id'] for group in groups]:
			expires = time.mktime(datetime.datetime.strptime(request.params['promotion.expiry'], "%Y-%m-%d").timetuple())
			if groups[id - 1]['requires_code']:
				code = request.params['promotion.code']
			else:
				code = None
			Settings.Session.add(Promotion(id, request.params['promotion.value'], request.params['promotion.name'], code, expires))
			try:
				Settings.Session.commit()
			except:
				Settings.Session.rollback()
	elif 'manage' in request.params:
		promotion = Settings.Session.query(Promotion).filter(Promotion.id == request.params['manage']).scalar()
		if promotion:
			action = {'action': 'manage', 'promotion': promotion}
	elif 'del' in request.params and validateCSRF(request):
		promotion = Settings.Session.query(Promotion).filter(Promotion.id == request.params['del']).scalar()
		if promotion:
			Settings.Session.delete(promotion)
			try:
				Settings.Session.commit()
			except:
				Settings.Session.rollback()
	elif 'update.submitted' in request.params and validateCSRF(request):
		promotion = Settings.Session.query(Promotion).filter(Promotion.id == request.params['promotion.id']).scalar()
		if promotion:
			promotion.expires = time.mktime(datetime.datetime.strptime(request.params['promotion.expiry'], "%Y-%m-%d").timetuple())
			if groups[promotion.type - 1]['requires_code']:
				promotion.code = request.params['promotion.code']
			else:
				promotion.code = None
			promotion.value = request.params['promotion.value']
			Settings.Session.query(Promotion).filter(Promotion.id == promotion.id).update({'name': promotion.name, 'value': promotion.value, 'expires': promotion.expires, 'code': promotion.code})
			try:
				Settings.Session.commit()
			except:
				Settings.Session.rollback()
	if not action:
		for group in groups:
			promotions = []
			for row in Settings.Session.query(Promotion).filter(Promotion.type == group['id']):
				promotions.append(row)
			group['promotions'] = promotions

	path = [{'name': 'Home', 'url': request.route_url('admin')}, {'name': 'Promotions', 'url': request.route_url('admin/promotions')}]
	
	return {'community': Settings.Community,  'path': path, 'permission': permission, 'groups': groups, 'action': action}
	
@view_config(route_name='admin/orders', renderer='templates/admin/orders.pt', permission='admin')
def viewOrders(request):
	path = [{'name': 'Home', 'url': request.route_url('admin')}, {'name': 'Orders', 'url': request.route_url('admin/orders')}]
	if(has_permission('root', Donate, request)):
		permission = 'root'
	else:
		permission = 'admin'
	if 'del' in request.params and validateCSRF(request):
		sub = Settings.Session.query(Subscriber).filter(Subscriber.id == request.params['del']).scalar()
		if sub:
			Settings.Session.delete(sub)
			try:
				Settings.Session.commit()
			except:
				Settings.Session.rollback()
	elif 'manage' in request.params:
		sub = Settings.Session.query(Subscriber).filter(Subscriber.id == request.params['manage']).scalar()
		if sub:
			return {'action': {'action': 'manage', 'sub': sub}, 'community': Settings.Community,  'path': path, 'permission': permission}
	elif 'add' in request.params:
		server = Settings.Session.query(Server).filter(Server.id == request.params['add']).scalar()
		if server:
			return {'action': {'action': 'add', 'server': server}, 'community': Settings.Community,  'path': path, 'permission': permission}
	elif 'save.submitted' in request.params:
		sub = Settings.Session.query(Subscriber).filter(Subscriber.id == request.params['sub.id']).scalar()
		if sub:
			sub.steamid = request.params['sub.steamid']
			sub.expires = time.mktime(datetime.datetime.strptime(request.params['sub.expires'], "%Y-%m-%d").timetuple())
			sub.item_id = request.params['sub.item']
			Settings.Session.query(Subscriber).filter(Subscriber.id == sub.id).update({'steamid': sub.steamid, 'expires': sub.expires, 'item_id': sub.item_id})
			try:
				Settings.Session.commit()
			except:
				Settings.Session.rollback()
	elif 'add.submitted' in request.params:
		Settings.Session.add(Subscriber(request.params['sub.sid'], request.params['sub.steamid'], request.params['sub.item'], time.mktime(datetime.datetime.strptime(request.params['sub.expires'], "%Y-%m-%d").timetuple())))
		try:
			Settings.Session.commit()
		except:
			Settings.Session.rollback()

	servers = Settings.Session.query(Server).all()
	
	return {'community': Settings.Community,  'path': path, 'permission': permission, 'action': {'action': None, 'servers': servers}}