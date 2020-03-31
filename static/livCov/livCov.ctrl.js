livCovApp.controller("livCovCtrl", ["LivCovService", function(LivCovService) {
	var self = this;

	self.query = {};
	
	self.setApp = function(app) {
		self.query.app = app;
	};

	self.reset = function() {
		return LivCovService.reset();
	};
	
	self.response = function() {
		return LivCovService.response();
	};

	self.submit = function() {
		return LivCovService.submit(self.query);
	};
	
	self.downloadUrl = function() {
		return "/result/" + self.response().result;
	};
	
	self.reset();
}]);