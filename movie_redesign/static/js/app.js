(() => {
  const root = document.documentElement;
  const saved = localStorage.getItem('cinema-theme');
  if (saved) root.dataset.theme = saved;

  const refreshIcons = () => window.lucide && lucide.createIcons();
  refreshIcons();

  document.querySelectorAll('[data-theme-toggle]').forEach(btn => btn.addEventListener('click', () => {
    root.dataset.theme = root.dataset.theme === 'light' ? 'dark' : 'light';
    localStorage.setItem('cinema-theme', root.dataset.theme);
    document.body.animate([{opacity:.9, filter:'blur(3px)'},{opacity:1,filter:'blur(0)'}], {duration:320,easing:'cubic-bezier(.22,.8,.2,1)'});
  }));

  document.querySelectorAll('.reveal-pass').forEach(btn => btn.addEventListener('click', () => {
    const input = btn.parentElement.querySelector('input');
    input.type = input.type === 'password' ? 'text' : 'password';
  }));

  document.querySelectorAll('.tilt-card').forEach(card => {
    let raf = 0;
    card.addEventListener('pointermove', e => {
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const r = card.getBoundingClientRect();
        const x = (e.clientX-r.left)/r.width-.5, y=(e.clientY-r.top)/r.height-.5;
        card.style.transform = `perspective(1100px) rotateX(${(-y*5).toFixed(2)}deg) rotateY(${(x*6).toFixed(2)}deg) translate3d(0,-3px,0)`;
      });
    });
    card.addEventListener('pointerleave', () => { cancelAnimationFrame(raf); card.style.transform=''; });
  });

  document.querySelectorAll('.magnetic').forEach(btn => {
    btn.addEventListener('pointermove', e => {
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
      const r=btn.getBoundingClientRect(), x=(e.clientX-(r.left+r.width/2))/r.width, y=(e.clientY-(r.top+r.height/2))/r.height;
      btn.style.transform=`translate(${(x*5).toFixed(1)}px,${(y*4).toFixed(1)}px)`;
    });
    btn.addEventListener('pointerleave',()=>btn.style.transform='');
  });

  document.querySelectorAll('[data-filter]').forEach(btn => btn.addEventListener('click', () => {
    document.querySelectorAll('[data-filter]').forEach(x=>x.classList.remove('active')); btn.classList.add('active');
    const f=btn.dataset.filter.toLowerCase();
    document.querySelectorAll('.movie-card').forEach(card => {
      const status=card.dataset.status, badge=card.dataset.badge, cat=card.dataset.category;
      let show=f==='all' ? status!=='ended' : f==='now showing' ? status==='now showing' : f==='pre-booking' ? status==='pre-booking' : f==='upcoming' ? ['releasing soon','pre-booking'].includes(status) : f==='trends' ? badge==='trending'||cat==='trends' : cat===f;
      card.style.display=show?'':'none';
    });
  }));

  document.querySelectorAll('[data-cinema-mode]').forEach(btn=>btn.addEventListener('click',()=>document.body.classList.toggle('cinema-mode')));
  document.querySelectorAll('[data-focus-mode]').forEach(btn=>btn.addEventListener('click',()=>document.body.classList.toggle('focus-mode')));
  document.querySelectorAll('[data-one-hand]').forEach(btn=>btn.addEventListener('click',()=>document.body.classList.toggle('one-hand')));

  const hour = new Date().getHours();
  document.body.dataset.timeMood = hour < 12 ? 'morning' : hour < 17 ? 'afternoon' : hour < 22 ? 'evening' : 'night';

  document.querySelectorAll('.enter-movie').forEach(link => link.addEventListener('click', e => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    e.preventDefault();
    document.body.classList.add('entering-movie');
    setTimeout(() => { window.location.href = link.href; }, 360);
  }));

  document.querySelectorAll('[data-qty-minus]').forEach(btn=>btn.addEventListener('click',()=>{const i=btn.parentElement.querySelector('input');i.value=Math.max(1,Number(i.value||1)-1)}));
  document.querySelectorAll('[data-qty-plus]').forEach(btn=>btn.addEventListener('click',()=>{const i=btn.parentElement.querySelector('input');i.value=Math.min(10,Number(i.value||1)+1)}));

  const seatForm=document.getElementById('seat-form');
  if(seatForm){
    const seats=[...seatForm.querySelectorAll('.seat input')], count=document.getElementById('seat-count'), view=document.getElementById('view-position');
    const update=()=>{const chosen=seats.filter(s=>s.checked); count.textContent=chosen.length; const xs=chosen.map(s=>Number(s.value.slice(1))); const avg=xs.length?xs.reduce((a,b)=>a+b,0)/xs.length:4.5; view.textContent=avg<3.2?'LEFT':avg>5.8?'RIGHT':'CENTER';};
    seats.forEach(input=>input.addEventListener('change',()=>{input.closest('.seat').classList.toggle('seat-selected',input.checked);update()})); update();
  }
})();
