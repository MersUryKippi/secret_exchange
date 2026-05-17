/* Secret Exchange — main.js */

/* ─── Countdown Timer ───────────────────────────────────────────────── */
function startTimer(seconds, displayId, barId) {
  const display = document.getElementById(displayId);
  const bar     = document.getElementById(barId);
  if (!display) return;

  let remaining = seconds;

  function fmt(s) {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, '0')}`;
  }

  display.textContent = fmt(remaining);

  const interval = setInterval(() => {
    remaining -= 1;
    if (remaining <= 0) {
      clearInterval(interval);
      display.textContent = '0:00';
      // Soft fade-out of the reveal box
      const reveal = document.querySelector('.secret-reveal');
      if (reveal) reveal.style.transition = 'opacity 1s ease';
      if (reveal) reveal.style.opacity = '0.2';
      if (bar)    bar.classList.add('urgent');
      display.textContent = 'истёк';
    } else {
      display.textContent = fmt(remaining);
      if (remaining <= 60 && bar) bar.classList.add('urgent');
    }
  }, 1000);
}

/* ─── Burn Confirm ───────────────────────────────────────────────────── */
const burnForm = document.getElementById('burn-form');
if (burnForm) {
  burnForm.addEventListener('submit', (e) => {
    const reveal = document.querySelector('.secret-reveal');
    if (reveal) {
      e.preventDefault();
      reveal.classList.add('burn-animation');
      setTimeout(() => burnForm.submit(), 900);
    }
  });
}

/* ─── Delete Confirm ─────────────────────────────────────────────────── */
const deleteForm = document.getElementById('delete-form');
if (deleteForm) {
  const btn = deleteForm.querySelector('button[type="submit"]');
  if (btn) {
    btn.addEventListener('click', () => {
      btn.textContent = 'Удаляем…';
      btn.disabled = true;
    });
  }
}