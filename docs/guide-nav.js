(function(){
  var pairs=[];
  document.querySelectorAll('nav.rail a').forEach(function(a){
    var el=document.getElementById(a.getAttribute('href').slice(1));
    if(el) pairs.push({link:a,el:el});
  });
  if(!pairs.length) return;
  var ticking=false;
  function sync(){
    ticking=false;
    var marker=window.innerHeight*0.22, active=pairs[0];
    pairs.forEach(function(p){
      if(p.el.getBoundingClientRect().top<=marker) active=p;
    });
    pairs.forEach(function(p){p.link.classList.toggle('on',p===active);});
  }
  function onScroll(){if(!ticking){ticking=true;requestAnimationFrame(sync);}}
  addEventListener('scroll',onScroll,{passive:true});
  addEventListener('resize',onScroll,{passive:true});
  sync();
})();
