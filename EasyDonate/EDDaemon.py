from . import Settings
from .ORM import Subscriber
import time

def main():
	while True:
		Settings.Session.query(Subscriber).filter(Subscriber.expires < time.time(), Subscriber.expires > 0).delete()
		try:
			Settings.Session.commit()
		except:
			Settings.Session.rollback()
		Settings.Session.remove()
		time.sleep(600)