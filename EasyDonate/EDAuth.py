from sqlalchemy import create_engine
from . import Settings
from .ORM import User
from passlib.hash import pbkdf2_sha512 as password_hash

def login(userid, password):
	for row in Settings.Session.query(User).filter(User.user == userid):
		if password_hash.verify(password, row.password):
			return True
	return False
	
def groups(userid, request):
	for row in Settings.Session.query(User).filter(User.user == userid):
		return row.groups.split(',')
	return None