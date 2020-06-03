livCovApp.controller("livCovCtrl", ["LivCovService", function(LivCovService) {
	var self = this;

	self.query = {
			"target_mass": 50.0,
			"temp_deck": "Temperature Module",
			"vol_scale": 0.5
	};
	
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