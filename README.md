# DiOS Backend

The DiOS backend provides a JSON-API to control the DiOS system. It provides a webinterface which allows easy scheduling of apps for execution and allows to take a look at the overall system status.

##Dependencies:

 * MongoDB
 * Python
	- flask, web framework
	- pymongo, mongodb access layer for python
	- mongokit, document based layer on top of pymongo
	- flask-mongokit, flask plugin for easy mongokit integration
	- requests (only needed for tests)

Just start the mongodb with `mongod` and run `backend.py`



##Install HowTo:

### Install required dependencies
```
aptitude install mongodb 
```

Since we need current versions of some python package we have to use `pip` instead of `apt`-packages

```
apt-get install build-essential python-dev python-pip  
pip install flask
pip install mongokit
pip install flask-mongokit
```

##### MongoDB security
mongos will listen only to local connections by default. It's possible to enable authentication - just add the credentials to `backend.cfg`.


### Apache2 and mod_wsgi
To run the backbend via apache2 mod_wsgi is needed.

```
apt-get install libapache2-mod-wsgi
```

The following apache config can be put at `/etc/apache2/conf.d/backend.conf`

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


## Known issues

 * The interface to store results is not that great for huge binary files (> 1GB) (Some apps will produce such big tcpdump results)
 

