progressApp.controller('progressInstanceCtrl', ["$scope", "$uibModalInstance", "ErrorService", "progressTitle", "cancel", "update", function($scope, $uibModalInstance, ErrorService, progressTitle, cancel, update) {
	var self = this;
	self.progressTitle = progressTitle;
	self.cancel = cancel;
	self.update = update;

	self.doCancel = function() {
		self.cancel().then(
			function(resp) {
				self.close();
			},
			function(errResp) {
				ErrorService.open(errResp.data.message);
			});
	};

	self.close = function() {
		$uibModalInstance.close();
	};
}]);