from setuptools import setup, find_packages

setup(
	name='EasyDonate',
	version='1.0.0+dev1748',
	author='Dreae',
	author_email='dreae@easydonate.tk',
	packages=find_packages(),
	package_data={'EasyDonate': ['templates/*.pt', 'templates/admin/*.pt', 
								'static/lib/*.js', 'static/css/*.css',
								'static/css/img/*', 'static/bootstrap/css/*',
								'static/bootstrap/fonts/*', 'static/bootstrap/js/*',
								'Config/settings.ini']},
	url='http://easydonate.tk',
	license='MIT License',
	description='Provides game communities the ability to accept donations',
	install_requires=['requests', 'sqlalchemy', 'pyramid', 'passlib', 'pymysql',
						'paypalrestsdk', 'pyramid_chameleon', 'certifi'],
)