#!/usr/bin/python

from flask import Flask, request, abort, send_from_directory, json, current_app
from bson import json_util
from bson.dbref import DBRef

from werkzeug.exceptions import default_exceptions
from werkzeug.exceptions import HTTPException
from werkzeug.wsgi import wrap_file

from mongokit import ObjectId
from flask.ext.mongokit import MongoKit
from documents import Job, App, AppStoreApp, CydiaApp, Run, Result, Worker, Account, Device

import logging
import base64
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('Backend')

#logger.setLevel(level=logging.DEBUG)


########
#some specal handling to enable json encoding of responses

__all__ = ['make_json_app']


def jd(obj):
	return json.dumps(obj, default=json_util.default)

def jl(obj):
	return json.loads(obj, object_hook=json_util.object_hook)

#
# Response
#
def response(data={}, code=200):
	return (jd(data), code, {'Content-Type':'application/json'})

def response_doc(doc):
	return response(doc.clean_doc())

def response_doc_list(docList, dictKey='_id'):
	return response(dict((str(doc[dictKey]), doc.clean_doc()) for doc in docList))

def response_file(fileobj, filename=None, cache_for=31536000, mimetype=None):
	if not mimetype:
		mimetype = fileobj.content_type
	if not mimetype:
		mimetype = 'application/octet-stream'
	headers = {}
	if filename:
		headers['Content-Disposition'] = 'attachment; filename="%s"' % filename
	data = wrap_file(request.environ, fileobj, buffer_size=1024 * 256)
	response = current_app.response_class(
		data,
		mimetype=mimetype,
		headers=headers,
		direct_passthrough=True)

	response.content_length = fileobj.length
	response.last_modified = fileobj.upload_date
	response.set_etag(fileobj.md5)
	response.cache_control.max_age = cache_for
	response.cache_control.s_max_age = cache_for
	response.cache_control.public = True
	response.make_conditional(request)
	return response

def make_json_app(import_name, **kwargs):
	"""
	Creates a JSON-oriented Flask app.

	All error responses that you don't specifically
	manage yourself will have application/json content
	type, and will contain JSON like this (just an example):

	{ "message": "405: Method Not Allowed" }
	"""
	def make_json_error(ex):
		status_code = (ex.code if isinstance(ex, HTTPException) else 500)
		data = {
			"message": str(ex),
#			"status":status_code
		}
		return response(data, status_code)

	app = Flask(import_name, **kwargs)

	for code in default_exceptions.iterkeys():
		app.error_handler_spec[None][code] = make_json_error

	return app




#######################

##
## The backend
##

AABACKEND_SETTINGS_ENV_KEY = 'AABACKEND_SETTINGS'
AABACKEND_BASEDIR_ENV_KEY = 'AABACKEND_BASEDIR'
AABACKEND_BASEDIR = './'

# create the application object
app = make_json_app("AABackend")

# setup basedir
if AABACKEND_BASEDIR_ENV_KEY in os.environ:
	AABACKEND_BASEDIR = os.environ[AABACKEND_BASEDIR_ENV_KEY]

if AABACKEND_SETTINGS_ENV_KEY in os.environ:
	app.config.from_envvar(AABACKEND_SETTINGS_ENV_KEY)
else:
	app.config.from_pyfile('backend.cfg')

# connect to the database
#db = Connection(Model.config.get('backend', 'dburi'))
db = MongoKit(app)
db.register([Worker, Job, App, AppStoreApp, CydiaApp, Run, Result, Account, Device])

# This will prevent errors due to missing dbref info
# just instantiate each document once
# especially: this will prevent getandsetworker to fail once
with app.app_context():
	for doc in db.registered_documents:
		db[doc.__name__]()


###
### REST API
###

# serve the frontend
@app.route('/')
@app.route('/<path:filepath>', methods=["GET"])
def serve_frontend(filepath='index.html'):
	return send_from_directory("%s/www" % AABACKEND_BASEDIR, filepath)



#
# App
#

@app.route('/apps', methods=["GET"])
def get_apps():
	appList = []
	appList += db.AppStoreApp.fetch({'type': 'AppStoreApp'})
	appList += db.CydiaApp.fetch({'type': 'CydiaApp'})
	if not appList or len(appList) == 0:
		abort(404, 'No apps found')

	return response_doc_list(appList, '_id')


def _get_apps_id_doc(objid):
	app = None
	try:
		app = db.AppStoreApp.fetch_one({'_id':objid, 'type': 'AppStoreApp'})
		if not app:
			app = db.CydiaApp.fetch_one({'_id':objid, 'type': 'CydiaApp'})
		if not app:
			abort(404, 'No apps found')
	except Exception as e:
		logger.error(e)
		abort(400, str(e))
	return app


@app.route('/apps/<ObjectId:objid>', methods=["GET"])
def get_apps_id(objid):
	return response_doc(_get_apps_id_doc(objid))


@app.route('/apps/bundleid/<bundleId>', methods=["GET"])
def get_apps_bundleId(bundleId):
	query = {'bundleId':bundleId}
	if 'version' in request.values:
		query['version'] = request.values['version']
	logger.debug('get app via bundleId. query: %s' % query)

	appList = []
	query['type'] = 'AppStoreApp'
	appList += db.AppStoreApp.fetch(query)
	query['type'] = 'CydiaApp'
	appList += db.CydiaApp.fetch(query)
	if not appList or len(appList) == 0:
		abort(404, 'No app found for bundleId %s' % bundleId)
	return response_doc_list(appList, '_id')


@app.route('/apps/<ObjectId:objid>/ipa', methods=["GET"])
def get_apps_ipa(objid):
	app = _get_apps_id_doc(objid)
	filename = str(objid)+'.ipa'
	if not app.fs.exists({'filename': filename}):
		abort(404, 'No ipa file found')
	return response_file(app.fs.get_last_version(filename=filename), filename='%s.ipa' % app.bundleId)


@app.route('/apps/<ObjectId:objid>/ipa', methods=["POST", "PUT"])
def post_apps_ipa(objid):
	files = request.files
	if not files:
		abort(400, 'no file received')
	if len(files) != 1:
		abort(400, 'invaild file data (please send exactly one file)')

	app = _get_apps_id_doc(objid)
	filename = str(objid)+'.ipa'
	
	if app.fs.exists({'filename': filename}):
		abort(400, 'file already present')
		
	ipa = files.values()[0]
	app.save()

	f = app.fs.new_file(filename)
	f.write(ipa)
	f.close()
	try:
		app.save()
	except Exception as e:
		logger.error(e)
		abort(400, str(e))

	return response({
		"message": "OK",
		"appId": str(app['_id'])
	})

@app.route('/apps', methods=["POST"])
@app.route('/apps/appstore', methods=["POST"])
def post_apps_appstore():

	app = db.AppStoreApp()
	data = app.rebuild_doc_dict(db, request.json)
	if not data:
		abort(400, 'No data received')

	query = {
		'bundleId': data['bundleId'],
		'version': data['version']
	}
	dbApp = db.AppStoreApp.find_one(query)
	if dbApp:
		app = dbApp
	app.update(data)
	try:
		app.save()
	except Exception as e:
		logger.error(e)
		abort(400, str(e))
	return response({
		"message": "OK",
		"appId": str(app['_id'])
	})

@app.route('/apps/cydia', methods=["POST"])
def post_apps_cydia():
	app = db.CydiaApp()
	data = app.rebuild_doc_dict(db, request.json)
	if not data:
		abort(400, 'No data received')
	app.update(data)
	try:
		app.save()
	except Exception as e:
		logger.error(e)
		abort(400, str(e))
	return response({
		"message": "OK",
		"appId": str(app['_id'])
	})


#
#	Job
#
@app.route('/jobs', methods=["GET"])
def get_jobs():
	query = {}
	state = Job.STATE.values()
	for param in state :
		if param in request.values :
			value = request.values[param]
			if (value.lower() == 'false') :
				state.remove(param)
	query['state'] = {'$in' : state }

	if 'bundleId' in request.values :
		query['bundleId'] = request.values['bundleId']

	cursor = db.Job.find(query)
	if not cursor or cursor.count() == 0:
		abort(404, 'No jobs found for given criteria')

	return response_doc_list(cursor)



# this method will return a suitable job for given worker and device or fail with 204 if currently no job available
@app.route('/jobs/getandsetworker/<ObjectId:workerId>/device/<deviceUDID>', methods=["GET"])
def get_and_set_worker(workerId, deviceUDID):
	jobFound = False

	worker = db.Worker.get_or_404(workerId)
	workerRef = DBRef(collection=worker.__collection__, id=workerId, database=worker.__database__)
	# use this DBRef instead of the worker doc due to $set is unable to set documents
#	logger.debug('worker found: %s' % str(worker['_id']))

	device = db.Device.find_one_or_404({'udid': deviceUDID})
	deviceRef = DBRef(collection=device.__collection__, id=device['_id'], database=device.__database__)
	# use this DBRef instead of the device doc due to $set is unable to set documents
#	logger.debug('device found: %s' % str(device['_id']))

	# check for jobs with worker and device set but unfinished
	job = db.Job.find_one({
		"worker.$id": workerId, # IDEA: should the worker be ignored to allow the job to switch the worker?
		"device.$id": device["_id"],
		"state": {"$nin": [Job.STATE.FINISHED, Job.STATE.FAILED]}
	})
	if job:
		jobFound = True
		logger.debug('found an unfinished job <%s> for device <%s>' % (str(job['_id']), str(device['_id'])))


	query = {
		"$or": [
			{"worker": {"$type":10}}, # worker has to be NULL
			{"worker.$id": workerId} # or the current worker
		],
		"$or": [
			{"device": {"$type":10}}, # device has to be NULL
			{"device.$id": device["_id"]} # or the current device
		],
		"state": {"$nin": [Job.STATE.FINISHED, Job.STATE.FAILED]},
		"_id": {"$nin":[]} # job blacklist for jobs unable to run on the given device
	}

	while not jobFound:
		# gat a job and set the worker within an atomic operation to guarantee consistency
		job = db.Job.find_and_modify(query=query, update={'$set': {'worker':workerRef, 'device':deviceRef}}, sort=[('date_added',-1)], new=True)

		if not job or not '_id' in job:
			return response(data={'message':'Currently no free job available'}, code=204)

		if job.can_run_on_device(device):
			jobFound = True
		else:
			print "DEBUG: job is unable to run on device \njob: %s\ndevice: %s" % (job, device)
			# reset the jobs worker entry
			db.Job.collection.update({"_id":ObjectId(job['_id'])}, {"$set": {"worker":None, "device":None}})
			# add the current job to the blacklist
			query['_id']['$nin'].append(ObjectId(job['_id']))

	return response_doc(job)


@app.route('/jobs/<ObjectId:objid>', methods=["GET"])
def get_jobs_id(objid):
	doc = db.Job.get_or_404(objid)
	return response_doc(doc)


@app.route('/jobs', methods=["POST"])
def post_jobs():

	job = db.Job()
	data = job.rebuild_doc_dict(db, request.json)
	if not data:
		abort(400, 'No data received')
	job.update(data)
	try:
		job.save()
	except Exception as e:
		logger.error(e)
		abort(400, str(e))
	return response({
		"message": "OK",
		"jobId": str(job['_id'])
	})


#
# Result
#
@app.route('/results', methods=["GET"])
def get_results():
	query = {}
	if 'runId' in request.values :
		query['run.$id'] = request.values['runId']
	if 'resultType' in request.values:
		query['resultInfo.type'] = request.values['resultType']

	cursor = db.Result.find(query)
	if not cursor or cursor.count() == 0:
		abort(404, 'No results found for given criteria')
	return response_doc_list(cursor)


@app.route('/results/<ObjectId:objid>', methods=["GET"])
def get_results_id(objid):
	doc = db.Result.get_or_404(objid)
	return response_doc(doc)


@app.route('/results/<ObjectId:objid>/binary', methods=["GET"])
def get_results_id_apparchive(objid):
	result = db.Result.get_or_404(objid)
	resultType = result.resultInfo.type
	if not (resultType == Result.TYPE.APP_ARCHIVE or resultType == Result.TYPE.TCPDUMP):
		abort(404, 'result contains no %s binary' % resultType)

	filename = '%s_%s' % (resultType, str(objid))
	if not result.fs.exists({'filename': filename}):
		abort(404, 'No file found')
	fileExtension = ""
	if resultType == Result.TYPE.APP_ARCHIVE:
		fileExtension = "zip"
	elif resultType == Result.TYPE.TCPDUMP:
		fileExtension = "pcap"
	return response_file(result.fs.get_last_version(filename=filename), filename='%s.%s' % (filename, fileExtension))


@app.route('/results', methods=["POST"])
def post_results():
	result = db.Result()
	data = result.rebuild_doc_dict(db, request.json)
	if not data:
		abort(400, 'No data received')
	result.update(data)

	# check for app_archive and save it to gridfs instead
	if 'type' in result.resultInfo:
		resultType = result.resultInfo['type']
		if resultType == Result.TYPE.APP_ARCHIVE or resultType == Result.TYPE.TCPDUMP:
	
			data = result.resultInfo['data']
			result.resultInfo['data'] = resultType.upper()
			try:
				result.save()
			except Exception as e:
				logger.error(e)
				abort(400, str(e))
	
			try:
				data = base64.b64decode(data)
				f = result.fs.new_file('%s_%s' % (resultType, result['_id']))
				f.write(data)
				f.close()
			except TypeError:
				logger.debug('unable to b64decode %s (result <%s>)' % (resultType, doc['_id']))

	try:
		result.save()
	except Exception as e:
		logger.error(e)
		abort(400, str(e))

	return response({
		"message": "OK",
		"resultId": str(result['_id'])
	})


## some special results methods
@app.route('/results/criteria', methods=["GET"])
def get_results_criteria():
	query = {
		'resultInfo.type': Result.TYPE.CRITERIA
	}
	cursor = db.Result.find(query)
	if not cursor or cursor.count() == 0:
		abort(404, 'No results found for given criteria')

	#build criteria result dict
	results = []

	for resultDoc in cursor:
		result = {}

		# add result id
		result['result'] = str(resultDoc['_id'])
		
		# add full run doc
		result['run'] = db.Run.fetch_one({'_id':resultDoc.run['_id']}).clean_doc()

		# add criteria data
		result['criteria'] = resultDoc.resultInfo.data
		# add app info
		## necessary to get the concrete type and not just an App document
		appId = resultDoc.run.app['_id']
		result['app'] = _get_apps_id_doc(appId).clean_doc()

		results.append(result)

	return response(results)

@app.route('/results/criteria/grouped', methods=["GET"])
def get_results_criteria_grouped():
	query = {
		'resultInfo.type': Result.TYPE.CRITERIA
	}
	cursor = db.Result.find(query)
	if not cursor or cursor.count() == 0:
		abort(404, 'No results found for given criteria')

	#build criteria result dict
	results = {}

	for resultDoc in cursor:

		appId = resultDoc.run.app['_id']
		appIdStr = str(appId)
		if appIdStr in results: #merge result
			result = results[appIdStr]
			# add result/run id
			result['results'].append(str(resultDoc['_id']))
			result['runs'].append(str(resultDoc.run['_id']))
			# combine criteria data
			criteria = result['criteria']
			dataDict = resultDoc.resultInfo.data
			for key in dataDict:
				value = dataDict[key]
				if key in criteria:
					value |= criteria[key]
				criteria[key] = value

		else: #add new app result
			result = {}
			# add result/run id
			result['results'] = [str(resultDoc['_id'])]
			result['runs'] = [str(resultDoc.run['_id'])]
			# add criteria data
			result['criteria'] = resultDoc.resultInfo.data
			# add app info
			## necessary to get the concrete type and not just an App document
			result['app'] = _get_apps_id_doc(appId).clean_doc()

			results[appIdStr] = result

	return response(results)

@app.route('/results/coverage', methods=["GET"])
def get_results_coverage():
	#build coverage result dict
	results = []
	
	appCursor = db.App.find()
	for app in appCursor:
		
		coverageDataDict = {}

		runCursor = db.Run.find({'app.$id':app['_id']})
		for run in runCursor:
			
			executionStrategy = run['executionStrategy']
			if executionStrategy != None:
				resultCursor = db.Result.find({'run.$id':run['_id'], 'resultInfo.type': Result.TYPE.COVERAGE})
				for result in resultCursor:
					ratioString = result['resultInfo']['data']
					ratioArray = ratioString.split("/") 
					if len(ratioArray) == 2:
						ratio = float(ratioArray[0])/float(ratioArray[1])
						if executionStrategy not in coverageDataDict or ratio > coverageDataDict[executionStrategy]:
							coverageDataDict[executionStrategy] = ratio

		# add coverage data
		for executionStrategy,ratio in coverageDataDict.items():
			result = {
				"bundleId": app['bundleId'],
				"genre": app['primaryGenreName'],
				"executionStrategy": executionStrategy,
				"coverage": ratio
			}
			results.append(result)
	
	return response(results)


@app.route('/results/trackinglibs', methods=["GET"])
def get_results_trackinglibs():
	#build result dict
	results = []

	appCursor = db.App.find()
	for app in appCursor:

		appDataDict = { 
		# add empty entries for all apps to allow ratio computation afterwards
			"OpenCloseExecution":[],
			"RandomExecution":[],
			"SmartExecution3":[],
			"SmartExecution5":[],
		}

		runCursor = db.Run.find({'app.$id':app['_id']})
		for run in runCursor:

			executionStrategy = run['executionStrategy']
			if executionStrategy != None:
				resultCursor = db.Result.find({'run.$id':run['_id'], 'resultInfo.type': Result.TYPE.TRACKING_LIBS})
				
				dataArray = None
				if executionStrategy in appDataDict:
					dataArray = appDataDict[executionStrategy]
				for result in resultCursor:
					libArray = result['resultInfo']['data']
					if not dataArray:
						dataArray = libArray
					else:
						for lib in libArray:
							if lib not in dataArray:
								dataArray.append(lib)
				if dataArray:
					appDataDict[executionStrategy] = dataArray

		# add data
		for executionStrategy,dataArray in appDataDict.items():
			result = {
				"bundleId": app['bundleId'],
				"genre": app['primaryGenreName'],
				"executionStrategy": executionStrategy,
				"tracking_libs": dataArray
			}
			results.append(result)

	return response(results)

@app.route('/results/httprequests', methods=["GET"])
def get_results_httprequests():
	#build result dict
	results = []

	appCursor = db.App.find()
	for app in appCursor:	
		appDataDict = {}
	
		runCursor = db.Run.find({'app.$id':app['_id']})
		for run in runCursor:
			
			executionStrategy = run['executionStrategy']
			if executionStrategy != None:
				resultCursor = db.Result.find({'run.$id':run['_id'], 'resultInfo.type': Result.TYPE.HTTP_REQUESTS})
				
				
				####
				dataArray = None
				if executionStrategy in appDataDict:
					dataArray = appDataDict[executionStrategy]
					
				for result in resultCursor:
					requestArray = result['resultInfo']['data']
					if not dataArray:
						dataArray = requestArray
					else:
						for request in requestArray:
							if request not in dataArray:
								dataArray.append(request)
				if dataArray:
					appDataDict[executionStrategy] = dataArray
					
					
				#####
	
		# add data
		for executionStrategy,dataArray in appDataDict.items():
			result = {
				"bundleId": app['bundleId'],
				"genre": app['primaryGenreName'],
				"executionStrategy": executionStrategy,
				"http_requests": dataArray
			}
			results.append(result)

	return response(results)

@app.route('/results/stacktraces', methods=["GET"])
def get_results_stacktraces():
	#build result dict
	results = []

	appCursor = db.App.find()
	for app in appCursor:
	
		appDataDict = {}

		runCursor = db.Run.find({'app.$id':app['_id']})
		for run in runCursor:

			executionStrategy = run['executionStrategy']
			if executionStrategy != None:
				
				resultCursor = db.Result.find({'run.$id':run['_id'], 'resultInfo.type': Result.TYPE.STACKTRACE})

				####
				dataDict = None
				if executionStrategy in appDataDict:
					dataDict = appDataDict[executionStrategy]

				for result in resultCursor:
					traceDict = result['resultInfo']['data']
					if not dataDict:
						dataDict = traceDict
					else:
						for key,traceList in traceDict.items():
							if key in dataDict:
								for trace in traceList:
									dataDict[key].append(trace)
							else:
								dataDict[key] = traceList
				if dataDict:
					appDataDict[executionStrategy] = dataDict


				#####

		# add data
		for executionStrategy,dataArray in appDataDict.items():
			result = {
				"bundleId": app['bundleId'],
				"genre": app['primaryGenreName'],
				"executionStrategy": executionStrategy,
				"stacktraces": dataDict
			}
			results.append(result)

	return response(results)
	
#
#	Run
#
@app.route('/runs', methods=["GET"])
def get_runs():
	query = {}
	if 'appId' in request.values :
		query['app.$id'] = request.values['appId']
	if 'executionStrategy' in request.values:
		query['executionStrategy'] = request.values['executionStrategy']

	cursor = db.Run.find(query)
	if not cursor or cursor.count() == 0:
		abort(404, 'No results found for given criteria')
	return response_doc_list(cursor)


@app.route('/runs/<ObjectId:objid>', methods=["GET"])
def get_run_id(objid):
	doc = db.Run.get_or_404(objid)
	return response_doc(doc)


@app.route('/runs', methods=["POST"])
def post_run():
	run = db.Run()
	data = run.rebuild_doc_dict(db, request.json)
	if not data:
		abort(400, 'No data received')
	run.update(data)
	try:
		run.save()
	except Exception as e:
		logger.error(e)
		abort(400, str(e))
	return response({
		"message": "OK",
		"runId": str(run['_id'])
	})


#
#	Account
#
@app.route('/accounts', methods=["GET"])
def get_accounts():
	cursor = db.Account.find()
	if not cursor or cursor.count() == 0:
		abort(404, 'No results found for given criteria')
	return response_doc_list(cursor, 'uniqueIdentifier')


@app.route('/accounts/<int:uniqueIdentifier>', methods=["GET"])
def get_account_uid(uniqueIdentifier):
	doc = db.Account.find_one_or_404({'uniqueIdentifier':uniqueIdentifier})
	return response_doc(doc)


@app.route('/accounts/appleid/<appleId>', methods=["GET"])
def get_account_appleid(appleId):
	doc = db.Account.find_one_or_404({'appleId':appleId})
	return response_doc(doc)


@app.route('/accounts', methods=["POST"])
def post_account():
	acc = db.Account()
	data = acc.rebuild_doc_dict(db, request.json)
	if not data:
		abort(400, 'No data received')
	if 'uniqueIdentifier' in data:
		dbAcc = db.Account.find_one({'uniqueIdentifier': data['uniqueIdentifier']})
		if dbAcc:
			acc = dbAcc
	acc.update(data)
	try:
		acc.save()
	except Exception as e:
		logger.error(e)
		abort(400, str(e))
	return response({
		"message": "OK",
		"accountId": str(acc['uniqueIdentifier'])
	})

#
#	Device
#
@app.route('/devices', methods=["GET"])
def get_devices():
	query = {}
	if 'accountId' in request.values :
		query['account.$id'] = request.values['accountId']

	cursor = db.Device.find(query)
	if not cursor or cursor.count() == 0:
		abort(404, 'No results found for given criteria')
	return response_doc_list(cursor, 'udid')


@app.route('/devices/<udid>', methods=["GET"])
def get_device_udid(udid):
	doc = db.Device.find_one_or_404({'udid':udid})
	return response_doc(doc)


@app.route('/devices', methods=["POST"])
def post_device():
	dev = db.Device()
	data = dev.rebuild_doc_dict(db, request.json)
	if not data:
		abort(400, 'No data received')
	if 'udid' in data:
		dbDev = db.Device.find_one({'udid': data['udid']})
		if dbDev:
			dev = dbDev
	dev.update(data)
	try:
		dev.save()
	except Exception as e:
		logger.error(e)
		abort(400, str(e))
	return response({
		"message": "OK",
		"deviceId": str(dev['udid'])
	})


#
#	Worker
#
@app.route('/workers', methods=["GET"])
def get_workers():
	query = {}
	if 'deviceId' in request.values :
		query['device.$id'] = request.values['deviceId']
	if 'name' in request.values :
		query['name'] = request.values['name']

	cursor = db.Worker.find(query)
	if not cursor or cursor.count() == 0:
		abort(404, 'No results found for given criteria')
	return response_doc_list(cursor)


@app.route('/workers/<ObjectId:objid>', methods=["GET"])
def get_worker_id(objid):
	doc = db.Worker.get_or_404(objid)
	return response_doc(doc)


@app.route('/workers', methods=["POST"])
def post_worker():
	worker = db.Worker()
	data = worker.rebuild_doc_dict(db, request.json)
	if not data:
		abort(400, 'No data received')
	worker.update(data)
	try:
		worker.save()
	except Exception as e:
		logger.error(e)
		abort(400, str(e))
	return response({
		"message": "OK",
		"workerId": str(worker['_id'])
	})


#main: start if directly called
if __name__ == '__main__':
	app.run(host='0.0.0.0',port=8080,threaded = True)
