(function() {
  var marker = document.getElementById("js-test-marker");
  if (!marker) {
    marker = document.createElement("div");
    marker.id = "js-test-marker";
    marker.style.cssText = "position:fixed;bottom:0;right:0;background:green;color:white;padding:4px 8px;font-size:12px;z-index:9999;";
    document.body.appendChild(marker);
  }
  marker.textContent = "JS loaded: " + new Date().toLocaleTimeString();
  marker.style.background = "green";
})();
