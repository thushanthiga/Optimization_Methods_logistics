const fs = require("fs");
const html = fs.readFileSync("Person_1/optimization_map.html", "utf8");
const match = html.match(/var routeData = (.*?);\s*var matrixData = (.*?);\s*var locCoords = (.*?);/);
if (match) {
    const routeData = JSON.parse(match[1]);
    const matrixData = JSON.parse(match[2]);
    const locCoords = JSON.parse(match[3]);
    
    const fromPt = "Depot: Colombo";
    const toPt = "Depot: Galle";
    
    var fromTrucks = [];
    var toTrucks = [];
    for (var i = 0; i < routeData.length; i++) {
        var locs = routeData[i].locations.map(function(l) { return l.name; });
        if (locs.indexOf(fromPt) !== -1) fromTrucks.push(routeData[i]);
        if (locs.indexOf(toPt) !== -1) toTrucks.push(routeData[i]);
    }
    
    function distance(p1, p2) {
        var lat1 = p1[0], lon1 = p1[1], lat2 = p2[0], lon2 = p2[1];
        var p = 0.017453292519943295;
        var c = Math.cos;
        var a = 0.5 - c((lat2 - lat1) * p)/2 + 
                c(lat1 * p) * c(lat2 * p) * 
                (1 - c((lon2 - lon1) * p))/2;
        return 12742 * Math.asin(Math.sqrt(Math.max(0, a))); // Added max 0
    }
    
    var bestDist = Infinity;
    var bestFromNode = null;
    var bestToNode = null;
    var bestFromTruck = null;
    var bestToTruck = null;
    
    for (var i = 0; i < fromTrucks.length; i++) {
        for (var j = 0; j < toTrucks.length; j++) {
            var tFrom = fromTrucks[i];
            var tTo = toTrucks[j];
            for (var n1 of tFrom.locations) {
                for (var n2 of tTo.locations) {
                    var d = distance([n1.lat, n1.lon], [n2.lat, n2.lon]);
                    if (d < bestDist) {
                        bestDist = d;
                        bestFromNode = n1;
                        bestToNode = n2;
                        bestFromTruck = tFrom;
                        bestToTruck = tTo;
                    }
                }
            }
        }
    }
    
    console.log("bestDist:", bestDist);
    console.log("bestFromNode:", bestFromNode ? bestFromNode.name : null);
    console.log("bestToNode:", bestToNode ? bestToNode.name : null);
    
    function extractPath(truck, startName, endName) {
        var names = truck.locations.map(l => l.name);
        var idx1 = names.indexOf(startName);
        var idx2 = names.indexOf(endName);
        var start = Math.min(idx1, idx2);
        var end = Math.max(idx1, idx2);
        var path = [];
        for(var i=start; i<=end; i++) {
            path.push([truck.locations[i].lat, truck.locations[i].lon]);
        }
        if (idx1 > idx2) path.reverse();
        return path;
    }
    
    try {
        var path1 = extractPath(bestFromTruck, fromPt, bestFromNode.name);
        var path2 = extractPath(bestToTruck, bestToNode.name, toPt);
        console.log("SUCCESS");
    } catch(e) {
        console.error("ERROR:", e);
    }
}
