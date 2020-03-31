errorApp.controller('errorInstanceCtrl', function($uibModalInstance, error) {
	var self = this;
	self.error = error;

	self.close = function() {
		$uibModalInstance.close();
	};
});