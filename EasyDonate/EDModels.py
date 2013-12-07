from pyramid.security import Allow, Everyone, has_permission, authenticated_userid

class Donate(object):
	__name__ = None
	__parent__ = None
	__acl__ = [ (Allow, Everyone, 'view'),
				(Allow, 'admin', 'admin'),
				(Allow, 'superadmin', 'admin'),
				(Allow, 'superadmin', 'root') ]
	def __init__(self, request):
		self.userid = authenticated_userid(request)
		pass