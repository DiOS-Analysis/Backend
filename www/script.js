
//////////////////////////////////////////////////
//
// some JS utils
//
//////////////////////////////////////////////////

function index(obj,i) {
	return obj[i];
}

function valueFromObject(object, path) {
	return path.split('.').reduce(index, object);	
}


//////////////////////////////////////////////////
//
// notification utilities
//
//////////////////////////////////////////////////

function notify(options) {
	$('.notifications').notify(options).show();
}

function notifySuccess(message) {
	notify({
		'message': {
			'html': message
		}
	});
}

function notifyError(message) {
	notify({
		'type': 'error',
		'fadeOut': {
			'enabled': false
		},
		'message': {
			'html': message
		}
	});
}


//////////////////////////////////////////////////
//
// Some JSON helper function
//
//////////////////////////////////////////////////

function postJSON(url, data) {
	$.ajax({
		url: url,
		data: JSON.stringify(data),
		type :'POST',
		contentType : "application/json",
		dataType:'json',
		cache: false,	
		error: function(xhr, ajaxOptions, thrownError){
			notifyError('postJSON to ' + url + ' data: <pre>' + JSON.stringify(data) + '</pre> failed with ' + xhr.status + ': ' + xhr.statusText);
			console.log($.parseJSON(xhr.responseText).message);
		}
	});
}


//////////////////////////////////////////////////
//
// some backend submit helpers
//
//////////////////////////////////////////////////


function submitJob(job) {
	postJSON('jobs', job);
	notifySuccess('Submitted job to backend. The new job will be visible after a table reload.')
}

function rescheduleJob(jobId) {
	$.getJSON('jobs/' + jobId, function(job) {
		delete job._id;
		delete job.date_added;
		job.state = 'pending';
		
		submitJob(job);
	});
}

function scheduleInstallAppJob(appId, deviceId) {
	$.getJSON('apps/' + appId, function(app) {
		job = {
			'type': 'install_app',
			'jobInfo': {
				'bundleId': app.bundleId,
				'appType': app.type,
				'version': app.version,
			},
			'state': 'pending'
		}

		if (deviceId.length > 0) {
			job.device = deviceId;
		}
		submitJob(job);
	});
}

function scheduleRunAppJob(appId, deviceId) {
	$.getJSON('apps/' + appId, function(app) {
		job = {
			'type': 'run_app',
			'jobInfo': {
				'bundleId': app.bundleId,
				'appType': app.type,
				'version': app.version,
			},
			'state': 'pending'
		}

		if (deviceId.length > 0) {
			job.device = deviceId;
		}
		submitJob(job);
	});
}

function scheduleAppJob(jobType, options) {
	job = {
		'type': jobType,
		'jobInfo': {
			'appType': 'AppStoreApp',
		},
		'state': 'pending'
	};

	if (options.device !== undefined && options.device.length > 0) {
		job.device = device;
	}
	delete options.device;
	for (var key in options) {
		var value = options[key];
		if (value !== undefined && value.length > 0 && value !== "any") {
			job.jobInfo[key] = value;
		}
	}
	submitJob(job);
}


//////////////////////////////////////////////////
//
// load backend data into special elements
//
//////////////////////////////////////////////////

function loadDevices() {
	$.getJSON("devices", function(data) {
		deviceData = data;
		$.each(data, function(key, val) {
			item = '<option value="' + val.uuid + '">' + val.deviceInfo.DeviceName + '</option>';
			$('.deviceSelect').append(item);
		});
	});
}

function loadAccounts() {
	$.getJSON("accounts", function(data) {
		$.each(data, function(key, val) {
			item = '<option value="' + val.uniqueIdentifier + '">' + val.appleId + '</option>';
			$('.accountSelect').append(item);
		});

	});
}
		
function loadWorkers() {
	$.getJSON("workers", function(data) {
		$.each(data, function(key, val) {
			item = '<option value="' + val._id + '">' + val.name + '</option>';
			$('.workerSelect').append(item);
		});
	});
}
			

//////////////////////////////////////////////////
//
// popover / action helper functions
//
//////////////////////////////////////////////////

function installAppOnDevice(options) {
	scheduleAppJob('install_app', options);
}

function installAllOnDevice(options) {
	bundleIdPath = currBundleIdPath();
	for (i=0; i<results.length; i++) {
		bundleId = valueFromObject(results[i], bundleIdPath);
		options.bundleId = bundleId
		installAppOnDevice(options);
	}
}

function installAppOnDeviceFormSubmit(form) {
	bundleId = form.find(".bundleId").val();
	device = form.find(".deviceSelect").val();
	account = form.find(".accountSelect").val();
	installAppOnDevice({
		'bundleId': bundleId,
		'device': device,
		'accountId': account
	});
	$(".installApp").popover("hide");
}

function installAllAppsOnDeviceFormSubmit(form) {
	device = form.find(".deviceSelect").val();
	account = form.find(".accountSelect").val();
	installAllOnDevice({
		'device': device,
		'accountId': account
	});
	$(".installAll").popover("hide");
}

function executeAppOnDevice(options) { 
	scheduleAppJob('run_app', options);
}

function executeAllOnDevice(options) {
	bundleIdPath = currBundleIdPath();
	for (i=0; i<results.length; i++) {
		bundleId = valueFromObject(results[i], bundleIdPath);
		options.bundleId = bundleId;
		executeAppOnDevice(options);
	}
}

function executeAppOnDeviceFormSubmit(form) {
	bundleId = form.find(".bundleId").val();
	device = form.find(".deviceSelect").val();
	executionStrategy = form.find(".executionStrategySelect").val();
	account = form.find(".accountSelect").val();
	
	executeAppOnDevice({
		'bundleId': bundleId,
		'device': device,
		'executionStrategy': executionStrategy,
		'accountId': account
	});
	$(".executeApp").popover("hide");
}

function executeAllAppsOnDeviceFormSubmit(form) {
	device = form.find(".deviceSelect").val();
	executionStrategy = form.find(".executionStrategySelect").val();
	account = form.find(".accountSelect").val();
	executeAllOnDevice({
		'device': device,
		'executionStrategy': executionStrategy,
		'accountId': account
	});
	$(".executeAll").popover("hide");
}



//////////////////////////////////////////////////
//
// some generic table content rendering functions
//
//////////////////////////////////////////////////

function renderImage( data, type, full ) {
	return '<img src="'+data+'"></img>';
}






