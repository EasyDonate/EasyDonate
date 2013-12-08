[EasyDonate](http://easydonate.tk)
=================

EasyDonate is an open-source platform for gaming communities to
accept payment for services they provide.  It is designed to make
donating fast and simple for your players, and provides an extensive
API for writing custom applictations to interface with your donation
page.

Documentation is on it's way, but for now you can check out EasyDonate
for yourself by having a look at the [demo](http://demo.easydonate.tk/) 
or visiting the demo [admin center](http://demo.easydonate.tk/admin) and
logging in with the username 'demo' and password 'ezdonate'


The API
--------------

Requests to the EasyDonate API are done via HTTP GET in the following format
```
http://{application_url}/api/{interface}/{method}?key=XXXXXXXXXXXXXXX&params...
```
API calls will return json, to view a list of currently available API interfaces
click [here](http://demo.easydonate.tk/api/IEasyDonateAPI/GetAPIInterfaces/?key=42gGdp9EjuDKvJYWAQaweb3vlYNfMIXE)

The API is a work in progress, if you would like to see methods or interfaces added,
drop me a line or open up an issue.