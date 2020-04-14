var livCovApp = angular.module("livCovApp", ["ngRoute", "ui.bootstrap", "ui.bootstrap.modal", "errorApp", "progressApp"]);

livCovApp.config(function($routeProvider, $locationProvider) {
	$routeProvider.when("/", {
		controller: "livCovCtrl",
		controllerAs: "ctrl",
		templateUrl: "static/postNormalise/postNormalise.html",
		app: "PostNormalise"
	}).when("/postNormalise", {
		controller: "livCovCtrl",
		controllerAs: "ctrl",
		templateUrl: "static/postNormalise/postNormalise.html",
		app: "PostNormalise"
	})
	
	// Use the HTML5 History API:
    $locationProvider.html5Mode(true);
});