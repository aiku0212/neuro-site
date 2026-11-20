// Keeps the current tab in view when the tab row is too narrow to show every tab.
(function(){
  var tabs = document.querySelector('.bar .tabs');
  if (!tabs) return;
  var cur = tabs.querySelector('[aria-current="true"]');
  if (!cur || tabs.scrollWidth <= tabs.clientWidth) return;
  var left = cur.offsetLeft - tabs.offsetLeft - (tabs.clientWidth - cur.offsetWidth) / 2;
  tabs.scrollLeft = Math.max(0, left);
})();
