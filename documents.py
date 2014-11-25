from flask.ext.mongokit import Document
from mongokit import ObjectId, IS, OR, Collection
from bson.errors import InvalidId
import time
import logging

class Enum(dict):
	__getattr__ = dict.get
	def __init__(self, *l):
		for e in l:
			self[e.upper()] = e

	def values_both_types(self):
		''' return the values as str and unicode to
			be able to check aganinst both variants
		'''
		results = []
		for val in self.values():
			results.append(str(val))
			results.append(unicode(val))
		return results

logger = logging.getLogger('Backend.'+__name__)

DATABASE="AABackend"


class BackendDocument(Document):
	__database__ = DATABASE

	#	returns a copy of self!
	def clean_doc(self):
		cp = self.copy()
		if '_id' in self:
			cp = self.copy()
			cp['_id'] = str(self['_id'])
		return cp

#TODO handle everything here by inspectiong the structure dict!
	@classmethod
	def rebuild_doc_dict(cls, db, docDict):
#		print "rebuild_doc_dict!"
		if not docDict:
			return {}
		if '_id' in docDict:
			idVal = docDict['_id']
#			print "cls: " + str(cls) + " id: " + str(idVal)
			if isinstance(idVal, basestring):
				idVal = ObjectId(idVal)
				if idVal:
					docDict['_id'] = idVal
		return docDict

	# add str as authorized type
	Document.authorized_types.append(str)

	use_dot_notation = True
	use_autorefs = True


###


### add find_and_modify support for documents
# this will be available via mongokit in feature releases

# this method hast to be added to the collection
def collection_find_and_modify(self, *args, **kwargs):
	obj_class = kwargs.pop('wrap', None)
	doc = super(Collection, self).find_and_modify(*args, **kwargs)
	if obj_class:
		return self.collection[obj_class.__name__](doc)

# the document method
def document_find_and_modify(self, *args, **kwargs):
	return self.collection.find_and_modify(wrap=self._obj_class, *args, **kwargs)

if not hasattr(Document, 'find_and_modify'):
	Collection.find_and_modify = collection_find_and_modify
	Document.find_and_modify = document_find_and_modify

###


class Worker(BackendDocument):
	__collection__ = 'workers'

	structure = {
		'name': basestring
	}


# An Apple store-account
class Account(BackendDocument):
	__collection__ = 'accounts'
	structure = {
		'uniqueIdentifier': basestring,
		'appleId': basestring,
		'password': basestring,
		'storeCountry': basestring
	}
	indexes = [{
		'fields':['uniqueIdentifier'],
		'unique':True,
	},{
		'fields':['appleId'],
		'unique':True,
	}]


# A device (iPhone, ...)
class Device(BackendDocument):
	__collection__ = 'devices'
	structure = {
		'udid': basestring,
		'deviceInfo': dict,
		'accounts': [Account]
	}
	required_fields = ['udid', 'accounts', 'deviceInfo']
	indexes = [{
		'fields':['udid'],
		'unique':True,
	}]

	def clean_doc(self):
		cp = super(Device, self).clean_doc()
		accList = []
		if 'accounts' in self and self.accounts:
			for acc in self.accounts:
				accList.append(acc.uniqueIdentifier)
		cp['accounts'] = accList
		return cp

	@classmethod
	def rebuild_doc_dict(cls, db, docDict):
		docDict = super(Device, cls).rebuild_doc_dict(db, docDict)

		if 'accounts' in docDict:
			accList = []
			accIdList = docDict['accounts']
			for accId in accIdList:
				acc = db.Account.find_one({'uniqueIdentifier':accId})
				accList.append(acc)

			docDict['accounts'] = accList
		return docDict


# A job will be executed by a worker
class Job(BackendDocument):
	STATE = Enum(u'undefined', u'pending', u'running', u'finished', u'failed')
	TYPE = Enum(u'run_app', u'install_app')

	use_autorefs = True
	__collection__ = 'jobs'
	structure = {
		'type': IS(*TYPE.values_both_types()),
		'state': IS(*STATE.values_both_types()),
		'jobInfo': dict,
			#TODO accountId, bundleId, storeCountry, appType{AppStoreApp,CydiaApp}, executionStrategy{DefaultExecution,OpenCloseExecution,RandomExecution,SmartExecution}
		'worker': Worker,
		'device': Device,
		'date_added': float
	}
	required_fields = ['type', 'state', 'jobInfo']
	default_values = {
		'date_added': time.time,
		'state': STATE.UNDEFINED
	}
	indexes = [{
		'fields':['type', 'state'],
	}]

	def clean_doc(self):
		cp = super(Job, self).clean_doc()
		if 'worker' in self and self.worker:
			cp['worker'] = str(self.worker['_id'])
		if 'device' in self and self.device:
			cp['device'] = str(self.device['udid'])
		return cp

	@classmethod
	def rebuild_doc_dict(cls, db, docDict):
		docDict = super(Job, cls).rebuild_doc_dict(db, docDict)

		if 'worker' in docDict:
			workerId = docDict['worker']
			try:
				workerId = ObjectId(workerId)
			except InvalidId:
				return docDict

			worker = db.Worker.find_one({'_id':workerId})
			docDict['worker'] = worker

		if 'device' in docDict:
			deviceId = docDict['device']
			device = db.Device.find_one({'udid':deviceId})
			if device:
				docDict['device'] = device
			else:
				logger.debug('given string %s is not a device udid' % deviceId)
				try:
					deviceId = ObjectId(deviceId)
				except InvalidId:
					logger.debug('given string %s is not a deviceId' % deviceId)
				device = db.Device.find_one({'_id':deviceId})
				if device:
					docDict['device'] = device
		return docDict

	def can_run_on_device(self, device):
		if self.type == Job.TYPE.RUN_APP:
			jobInfo = self.jobInfo
			if 'accountId' in jobInfo:
				for acc in device.accounts:
					if jobInfo['accountId'] == acc.uniqueIdentifier:
						return True
				return False
			if 'storeCountry' in jobInfo:
				country = jobInfo['storeCountry']
				for acc in device.accounts:
					if country == acc.storeCountry:
						return True
				return False
		return True


# A app is a concrete app (user account, version, bundleID) under test
class App(BackendDocument):
	__collection__ = 'apps'
	type_field = 'type'
	structure = {
		'type': basestring,
		'name': basestring,
		'bundleId': basestring,
		'version': basestring,
		'date_added': float
	}
	gridfs = {
		'files': ['ipa']
	}
	required_fields = ['bundleId', 'version', 'type', 'name']
	default_values = {
		'date_added': time.time
	}
	indexes = [{
		'fields':['bundleId', 'version'],
		'unique':True,
	},{
		'fields':['name']
	}]

	# this will fix validation errors for superclass fields
	use_schemaless = True


class AppStoreApp(App):
	use_schemaless = True

	structure = {
		'trackId': OR(int, basestring),
		'account': Account,
		'price': OR(float, basestring),
	}
	required_fields = ['trackId', 'account']
	indexes = [{
		'fields':['bundleId', 'version'],
		'unique':True,
	},{
		'fields':['name']
	}]

	def clean_doc(self):
		cp = super(AppStoreApp, self).clean_doc()
		if 'account' in self and self.account:
			cp['account'] = str(self.account['uniqueIdentifier'])
		return cp

	@classmethod
	def rebuild_doc_dict(cls, db, docDict):
		docDict = super(AppStoreApp, cls).rebuild_doc_dict(db, docDict)

		if 'account' in docDict:
			acc = db.Account.find_one({
				'uniqueIdentifier': str(docDict['account'])
			})
			docDict['account'] = acc
		return docDict


class CydiaApp(App):
	structure = {
	}


# A run is a concrete app execution
class Run(BackendDocument):
	STATE = Enum(u'undefined', u'pending', u'running', u'finished')

	use_autorefs = True
	__collection__ = 'runs'
	structure = {
		'app': App,
		'state': IS(*STATE.values_both_types()),
		'executionStrategy': basestring,
		'date_added': float
	}
	required_fields = ['app']
	default_values = {
		'date_added': time.time
	}
	indexes = [{
		'fields':['state'],
	}]

	def clean_doc(self):
		cp = super(Run, self).clean_doc()
		if 'app' in self and self.app:
			cp['app'] = str(self.app['_id'])
		return cp

	@classmethod
	def rebuild_doc_dict(cls, db, docDict):
		docDict = super(Run, cls).rebuild_doc_dict(db, docDict)

		if 'app' in docDict:
			appId = docDict['app']
			try:
				appId = ObjectId(appId)
			except InvalidId:
				return docDict

			app = db.AppStoreApp.find_one({'_id':appId})
			if not app:
				app = db.CydiaApp.find_one({'_id':appId})

			docDict['app'] = app
		return docDict


# A result needs a corresponding run, multiple results per run are possible
class Result(BackendDocument):
	TYPE = Enum(u'app_archive', u'string', u'criteria', u'stacktrace', u'tcpdump', u'screenshot', u'coverage', u'tracking_libs', u'http_requests')

	__collection__ = 'results'
	structure = {
		'run': Run,
		'resultInfo': {
			'type': basestring,
			'data': None
		},
		'date_added': float
	}
	gridfs = {
		'files': ['apparchive']
	}
	required_fields = ['run']
	default_values = {
		'date_added': time.time
	}
	indexes = [{
		'fields':['resultInfo.type'],
	}]

	def clean_doc(self):
		cp = super(Result, self).clean_doc()
		if 'run' in self and self.run:
			cp['run'] = str(self.run['_id'])
		return cp

	@classmethod
	def rebuild_doc_dict(cls, db, docDict):
		docDict = super(Result, cls).rebuild_doc_dict(db, docDict)

		if 'run' in docDict:
			runId = docDict['run']
			try:
				runId = ObjectId(runId)
			except InvalidId:
				return docDict

			run = db.Run.find_one({'_id':runId})

			docDict['run'] = run
		return docDict


