# DiOS Backend

The DiOS Backend is the main component of DiOS and is responsible for centralized data storage. It holds configuration data such as App Store account credentials (to automatically purchase apps) and status information on available iOS analysis devices. Furthermore, it archives all app binaries of recent analysis and processes analysis results reported back from the iOS devices. The backend provides a JSON-API to control the entire DiOS system and to monitor the system status. Moreover, the backend provides a web-based interface to browse the App Store and to easily schedule apps for execution to available devices.

##Dependencies:

 * MongoDB
 * Python
	- flask, web framework
	- pymongo, mongodb access layer for python
	- mongokit, document based layer on top of pymongo
	- flask-mongokit, flask plugin for easy mongokit integration
	- requests (only required for testing)

To launch the DiOS backend component, just start the mongodb (`mongod`) and run `backend.py`.


##Install HowTo:

### Install Required Dependencies
```
aptitude install mongodb 
```

As DiOS requires up-to-date versions of some python packages, `pip` is preferred over `apt`-packages.

```
apt-get install build-essential python-dev python-pip  
pip install flask
pip install mongokit
pip install flask-mongokit
```

##### MongoDB Security
By default, mongodb listens to local connections only. Authentication may be enabled by adding credentials to `backend.cfg`.


### Optional: Apache2 and mod_wsgi
To run the DiOS backbend via apache2 the Apache module `mod_wsgi` is required.

```
apt-get install libapache2-mod-wsgi
```

The Apache configuration should be updates as follows (e.g., `/etc/apache2/conf.d/backend.conf`)

```
WSGIDaemonProcess AABackend user=www-data group=www-data threads=5  
WSGIScriptAlias /AABackend /opt/dios/Backend/backend.wsgi   
WSGIRestrictStdout Off
```

```   
<Directory /opt/dios/Backend/>   
  WSGIProcessGroup AABackend  
  WSGIApplicationGroup %{GLOBAL}  
  Order deny,allow   
  Allow from all   
</Directory>  
```



