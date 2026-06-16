function formatTime(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60).toString().padStart(2, '0');
  const seconds = (totalSeconds % 60).toString().padStart(2, '0');
  return `${minutes}:${seconds}`;
}
function startTimer(seconds) {
  let remaining = seconds;
  const el = document.getElementById('timer');
  if (!el) return;
  el.textContent = formatTime(remaining);
  const interval = setInterval(() => {
    remaining -= 1;
    el.textContent = formatTime(Math.max(remaining, 0));
    if (remaining <= 0) {
      clearInterval(interval);
      el.textContent = 'Готово';
    }
  }, 1000);
}
