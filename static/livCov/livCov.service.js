livCovApp.service("LivCovService", ["$http", "$rootScope", "ErrorService", "ProgressService", function($http, $rootScope, ErrorService, ProgressService) {
	var jobId = null;
	var jobResponse = null;
	
	this.reset = function() {
		jobResponse = {"update": {"status": "waiting", "message": "Waiting..."}};
	}
	
	this.response = function() {
		return jobResponse;
	};
	
	this.submit = function(query) {
		jobId = null;
		jobResponse = {"update": {"status": "submitting", "message": "Submitting..."}};
		error = null;
		
		ProgressService.open(query["app"] + " dashboard", this.cancel, this.update);
		
		$http.post("/submit", query).then(
			function(resp) {
				jobId = resp.data.job_id;
				listen();
			},
			function(errResp) {
				onerror(errResp.data.message);
			});
	};
	
	this.cancel = function() {
		return $http.get("/cancel/" + jobId);
	};
	
	this.update = function() {
		return jobResponse.update;
	};
	
	listen = function() {
		var source = new EventSource("/progress/" + jobId);

		source.onmessage = function(event) {
			jobResponse = JSON.parse(event.data);
			status = jobResponse.update.status;
			
			if(status == "cancelled" || status == "error" || status == "finished") {
				source.close();
				jobId = null;
			}
			
			$rootScope.$apply()
		};
		
		source.onerror = function(event) {
			source.close();
			jobId = null;
			onerror(event.message);
		}
	};
	
	onerror = function(message) {
		jobResponse.update.status = "error";
		jobResponse.update.message = "Error";
		ProgressService.close();
		ErrorService.open(message);
	};
	
	// Initialise:
	this.reset();
}]);