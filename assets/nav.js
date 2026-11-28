// Keeps the current tab in view when the tab row is too narrow to show every tab,
// and fades whichever edge has more tabs beyond it.
(function(){
  var tabs = document.querySelector('.bar .tabs');
  if (!tabs) return;
  function fade(){
    var max = tabs.scrollWidth - tabs.clientWidth;
    if (max <= 1){ tabs.removeAttribute('data-fade'); return; }
    var left = tabs.scrollLeft > 2, right = tabs.scrollLeft < max - 2;
    tabs.setAttribute('data-fade', left && right ? 'both' : left ? 'left' : right ? 'right' : 'none');
  }
  var cur = tabs.querySelector('[aria-current="true"]');
  if (cur && tabs.scrollWidth > tabs.clientWidth){
    var left = cur.offsetLeft - tabs.offsetLeft - (tabs.clientWidth - cur.offsetWidth) / 2;
    tabs.scrollLeft = Math.max(0, left);
  }
  fade();
  tabs.addEventListener('scroll', fade, { passive: true });
  window.addEventListener('resize', fade);
})();
