import {imagery} from './imagery.js?v=sunrise-1';

document.querySelectorAll('[data-image]').forEach(img => {
  const record = imagery[img.dataset.image];
  if (!record) return;
  img.src = record.src; img.width = record.w; img.height = record.h;
  img.alt = img.dataset.decorative ? '' : record.alt;
});

const $ = selector => document.querySelector(selector);
const dialog = $('#assistant'), textarea = $('#question'), form = $('#question-form');
const messages = $('#messages'), welcome = $('#assistant-welcome'), loading = $('#loading');
let opener = null, busy = false;

function openAssistant(question = '', trigger = null) {
  opener = trigger || document.activeElement;
  if (!dialog.open) dialog.showModal();
  document.body.classList.add('modal-open');
  if (question) textarea.value = question;
  updateCount(); textarea.focus();
}
function closeAssistant() { dialog.close(); }
dialog.addEventListener('close', () => { document.body.classList.remove('modal-open'); opener?.focus(); });
dialog.addEventListener('click', event => {
  const box = dialog.getBoundingClientRect();
  if (event.target === dialog && (event.clientX < box.left || event.clientX > box.right)) closeAssistant();
});
document.querySelectorAll('.assistant-trigger').forEach(button => button.addEventListener('click', () => openAssistant('', button)));
document.querySelectorAll('.prompt-trigger').forEach(button => button.addEventListener('click', () => openAssistant(button.dataset.question, button)));
$('#close-assistant').addEventListener('click', closeAssistant);
document.querySelectorAll('.suggestions button').forEach(button => button.addEventListener('click', () => { textarea.value = button.dataset.question; updateCount(); textarea.focus(); }));
$('#clear-chat').addEventListener('click', () => {
  if (busy) return;
  messages.replaceChildren(); welcome.hidden = false; textarea.value = ''; updateCount();
  $('#form-error').hidden = true; textarea.focus();
});
function updateCount() { $('#character-count').textContent = `${textarea.value.length} / 2000`; }
textarea.addEventListener('input', updateCount);
textarea.addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); if (!busy) form.requestSubmit(); } });
function scrollChat() { $('#chat-scroll').scrollTop = $('#chat-scroll').scrollHeight; }
function makeMessage(role, text, variant = '') {
  const block = document.createElement('article'); block.className = `message ${role} ${variant}`;
  const label = document.createElement('div'); label.className = 'message-label'; label.textContent = role === 'user' ? 'You' : 'Quantum Primer'; block.append(label);
  text.split(/\n\s*\n/).filter(Boolean).forEach(part => { const p = document.createElement('p'); p.textContent = part; block.append(p); });
  messages.append(block); return block;
}
function addSources(block, citations) {
  if (!citations.length) return;
  const details = document.createElement('details'); details.className = 'sources';
  const summary = document.createElement('summary'); summary.textContent = `Explore ${citations.length} source ${citations.length === 1 ? 'reference' : 'references'}`; details.append(summary);
  citations.forEach(citation => {
    const row = document.createElement('div'); row.className = 'source-row';
    const number = document.createElement('span'); number.className = 'source-number'; number.textContent = `[${citation.id}]`;
    const content = document.createElement('div'), title = document.createElement('strong'), author = document.createElement('p'), locator = document.createElement('p');
    title.textContent = citation.title; author.textContent = citation.author; locator.textContent = citation.locator;
    content.append(title, author, locator); row.append(number, content); details.append(row);
  });
  block.append(details);
}
async function sendQuestion(question, retry = false) {
  if (busy) return;
  question = question.trim();
  if (question.length < 3 || question.length > 2000) {
    $('#form-error').textContent = 'Please write a question between 3 and 2,000 characters.';
    $('#form-error').hidden = false; return;
  }
  $('#form-error').hidden = true; welcome.hidden = true; busy = true;
  if (!retry) makeMessage('user', question);
  textarea.value = ''; updateCount(); loading.hidden = false;
  $('.send-button').disabled = true; $('#clear-chat').disabled = true;
  scrollChat();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 240000);
  try {
    const response = await fetch('/api/ask', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({question}), signal: controller.signal});
    if (!response.ok) throw new Error('service');
    const answer = await response.json();
    if (!['answered', 'insufficient_context'].includes(answer.status) || typeof answer.answer !== 'string' || !Array.isArray(answer.citations)) throw new Error('response');
    const block = makeMessage('assistant', answer.answer, answer.status === 'insufficient_context' ? 'refusal' : '');
    addSources(block, answer.citations);
  } catch (error) {
    const block = makeMessage('assistant', error.name === 'AbortError' ? 'This is taking longer than expected. Please try the question again.' : 'I couldn’t reach the library just now. Please try again in a moment.', 'error');
    const button = document.createElement('button'); button.className = 'retry-button'; button.textContent = 'Try again';
    button.addEventListener('click', () => { if (!busy) { block.remove(); sendQuestion(question, true); } }); block.append(button);
  } finally {
    clearTimeout(timer); busy = false; loading.hidden = true; $('.send-button').disabled = false; $('#clear-chat').disabled = false; scrollChat();
  }
}
form.addEventListener('submit', event => { event.preventDefault(); sendQuestion(textarea.value); });

const topics = {
  'kruse-epi-paleo-rx': ['DHA, diet and the environment', 'How does Jack Kruse describe DHA in Epi-paleo Rx?'],
  'ott-health-and-light': ['Light and living systems', 'In Health and Light, how did John Ott study the effects of light on plants?'],
  'mcfadden-al-khalili-life-on-the-edge': ['A starting point for quantum biology', 'In Life on the Edge, how do the authors describe the magnetic compass of robins? Explain in plain language.'],
  'clinton-optimize': ['Water, light and biological energy', 'In Optimize, how does Catherine Clinton describe exclusion zone water?'],
  'lee-mitochondriac-manifesto': ['Mitochondria and biophysics', 'In The Mitochondriac Manifesto, how does R. D. Lee describe mitochondria?'],
  'hunt-your-spark-is-light': ['Fertilization and human creation', 'In Your Spark is Light, how does Courtney Hunt describe the zinc spark at fertilization?'],
};
async function loadLibrary() {
  const list = $('#book-list');
  try {
    const response = await fetch('/api/library'); if (!response.ok) throw new Error('library');
    const data = await response.json(); list.replaceChildren();
    data.sources.forEach((source, index) => {
      const row = document.createElement('article'); row.className = 'book'; row.id = `book-${source.id}`;
      const number = document.createElement('span'); number.className = 'plate'; number.textContent = String(index + 1).padStart(2, '0');
      const content = document.createElement('div'), title = document.createElement('h3'), author = document.createElement('p'), topic = document.createElement('p');
      title.textContent = source.title; author.textContent = source.author; topic.className = 'book-topic'; topic.textContent = topics[source.id]?.[0] || 'Explore this book';
      const guideName = document.createElement('p'), shortName = document.createElement('strong');
      guideName.className = 'book-guide-name'; guideName.append('Use in the guide: ');
      shortName.textContent = source.title.split(':')[0].trim(); guideName.append(shortName);
      const button = document.createElement('button'); button.textContent = '↗'; button.setAttribute('aria-label', `Ask about ${source.title}`);
      button.addEventListener('click', () => openAssistant(topics[source.id]?.[1] || `What ideas are discussed in “${source.title}”?`, button));
      content.append(title, author, guideName, topic); row.append(number, content, button); list.append(row);
    });
    if (!data.sources.length) list.textContent = 'Your library is empty. Add a book to begin exploring.';
  } catch {
    list.textContent = 'The reading room couldn’t be loaded. ';
    const retry = document.createElement('button'); retry.className = 'text-button'; retry.textContent = 'Try again'; retry.addEventListener('click', loadLibrary); list.append(retry);
  }
}
loadLibrary();

const themeButton = $('.theme-button');
function updateThemeButton() {
  const light = document.documentElement.dataset.theme === 'light';
  themeButton.textContent = light ? '☾' : '☼';
  themeButton.setAttribute('aria-label', `Switch to ${light ? 'dark' : 'light'} theme`);
}
updateThemeButton();
themeButton.addEventListener('click', () => { const theme = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light'; document.documentElement.dataset.theme = theme; try { localStorage.setItem('qp-theme', theme); } catch {} updateThemeButton(); });
const menuButton = $('.menu-button');
menuButton.addEventListener('click', () => { const open = $('#main-nav').classList.toggle('open'); menuButton.setAttribute('aria-expanded', String(open)); menuButton.setAttribute('aria-label', open ? 'Close menu' : 'Open menu'); });
$('#main-nav').addEventListener('click', event => { if (event.target.tagName === 'A') { $('#main-nav').classList.remove('open'); menuButton.setAttribute('aria-expanded', 'false'); menuButton.setAttribute('aria-label', 'Open menu'); } });
const credits = $('#credits');
$('#credits-trigger').addEventListener('click', () => { credits.showModal(); document.body.classList.add('modal-open'); });
$('.close-credits').addEventListener('click', () => credits.close());
credits.addEventListener('close', () => { document.body.classList.remove('modal-open'); $('#credits-trigger').focus(); });
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)');
let ticking = false;
function updateScroll() {
  $('.site-header').classList.toggle('scrolled', scrollY > 80);
  const section = $('.hero-scroll'), stage = $('.hero-stage');
  if (!reduceMotion.matches) {
    const distance = section.offsetHeight - stage.offsetHeight;
    const progress = Math.max(0, Math.min(1, -section.getBoundingClientRect().top / Math.max(1, distance)));
    // Start with the whole portrait visible, then follow its eye into the scene.
    const width = stage.clientWidth, height = stage.clientHeight;
    const fit = Math.min(width / 1024, height / 1536);
    const art = $('.hero-art img');
    const [positionX, positionY] = getComputedStyle(art).objectPosition.split(' ').map(value => parseFloat(value) / 100);
    const eyeX = (width - 1024 * fit) * positionX + 610 * fit;
    const eyeY = (height - 1536 * fit) * positionY + 470 * fit;
    const travel = Math.min(1, progress / .85);
    const scale = 1 + travel ** 3 * 27;
    art.style.transformOrigin = `${eyeX}px ${eyeY}px`;
    art.style.transform = `translate(${(width / 2 - eyeX) * travel}px, ${(height / 2 - eyeY) * travel}px) scale(${scale})`;
    art.style.filter = `blur(${Math.max(0, progress - .35) * 10}px)`;
    stage.style.opacity = String(1 - Math.max(0, (progress - .84) / .16));
    $('.hero-copy').style.opacity = String(Math.max(0, 1 - progress / .24));
    $('.hero-copy').style.transform = `translateY(${-Math.min(progress, .3) * 140}px)`;
    $('.hero-copy').inert = progress > .24;
    $('.hero-actions').style.pointerEvents = progress > .24 ? 'none' : 'auto';
    $('.hero-bottom').style.opacity = String(Math.max(0, 1 - progress / .2));
    $('.hero-shade').style.opacity = String(Math.max(0, 1 - progress / .5));
  } else {
    stage.style.opacity = '1';
    $('.hero-art img').style.transform = '';
    $('.hero-art img').style.filter = '';
    $('.hero-copy').style.transform = '';
    $('.hero-copy').style.opacity = '1';
    $('.hero-copy').inert = false;
    $('.hero-actions').style.pointerEvents = 'auto';
    $('.hero-bottom').style.opacity = '1';
    $('.hero-shade').style.opacity = '1';
  }
  ticking = false;
}
addEventListener('scroll', () => { if (!ticking) { requestAnimationFrame(updateScroll); ticking = true; } }, {passive:true});
addEventListener('resize', updateScroll); reduceMotion.addEventListener('change', updateScroll); updateScroll();
