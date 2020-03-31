livCovApp.directive("filereader", [function () {
    return {
        scope: {
        	"filereader": "=",
        	"filename": "="
        },
        link: function(scope, element, attributes) {
            element.bind("change", function(changeEvent) {
                var reader = new FileReader();
                
                reader.onload = function(loadEvent) {
                    scope.$apply(function() {
                        scope.filereader = loadEvent.target.result;
                    });
                }
                
                if(changeEvent.target.files[0]) {
                	scope.$apply(function() {
	                	scope.filename = changeEvent.target.files[0].name;
	                	reader.readAsText(changeEvent.target.files[0]);
                	});
                }
            });
        }
    }
}]);