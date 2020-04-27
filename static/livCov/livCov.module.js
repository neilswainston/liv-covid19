var livCovApp = angular.module("livCovApp", ["ngRoute", "ui.bootstrap", "ui.bootstrap.modal", "errorApp", "progressApp"]);

livCovApp.config(function($routeProvider, $locationProvider) {
	$routeProvider.when("/", {
		controller: "livCovCtrl",
		controllerAs: "ctrl",
		templateUrl: "static/opentrons/opentrons.html",
		app: "Opentrons"
	}).when("/opentrons", {
		controller: "livCovCtrl",
		controllerAs: "ctrl",
		templateUrl: "static/opentrons/opentrons.html",
		app: "Opentrons"
	}).when("/normalise", {
		controller: "livCovCtrl",
		controllerAs: "ctrl",
		templateUrl: "static/normalise/normalise.html",
		app: "Normalise"
	})
	
	// Use the HTML5 History API:
    $locationProvider.html5Mode(true);
});