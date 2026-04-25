/* === IELTS Interactive AI Correction — injected JS block === */
(function () {
  'use strict';

  // Substituted by make_interactive.py at build time.
  const AI_ENDPOINT = "__AI_ENDPOINT__";
  const PRONUNCIATIONS_URL = "__PRONUNCIATIONS_URL__";
  const LESSON_KEY = "__LESSON_KEY__"; // e.g. "Week_1_Lesson_Plan"

  const ns = (window.__ielts = window.__ielts || {});

  // ====================================================================
  // TTS subsystem — Web Speech API with voice waterfall + karaoke
  // ====================================================================

  // Common female-neural voice names across Edge/Chrome (Windows), Safari/iOS,
  // and Android system voices. Spec §8.1 voice waterfall.
  const FEMALE_NEURAL_UK = /Sonia|Libby|Mia|Maisie|Jenny.*GB|Kate|Serena/i;
  const MALE_NEURAL_UK   = /Ryan|Thomas.*GB|Noah|Daniel/i;
  const FEMALE_NEURAL_US = /Aria|Jenny|Ana|Michelle|Emma|Samantha|Allison|Ava/i;
  const MALE_NEURAL_US   = /Guy|Tony|Jason|Eric|Davis|Alex|Aaron/i;

  function pickVoice(lang) {
    if (!('speechSynthesis' in window)) return null;
    const all = window.speechSynthesis.getVoices();
    if (!all.length) return null;
    const langPrefix = lang === 'en-GB' ? 'en-GB' : 'en-US';
    const inLang = all.filter(v => v.lang === langPrefix);
    const female = lang === 'en-GB' ? FEMALE_NEURAL_UK : FEMALE_NEURAL_US;
    const male   = lang === 'en-GB' ? MALE_NEURAL_UK   : MALE_NEURAL_US;
    return inLang.find(v => female.test(v.name))
        || inLang.find(v => male.test(v.name))
        || inLang[0]
        || all[0];
  }

  function isWeChatBrowser() {
    return /MicroMessenger/i.test(navigator.userAgent || '');
  }

  function wechatFallbackAlert() {
    alert("微信浏览器不支持语音播放，请用 Safari 或 Chrome 打开本页 / WeChat browser doesn't support audio playback. Please open this page in Safari or Chrome.");
  }

  let _currentSpans = null;

  ns.stopSpeaking = function () {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    if (_currentSpans) _currentSpans.forEach(s => s.classList.remove('speaking'));
    _currentSpans = null;
  };

  ns.speakText = function (text, lang = 'en-GB', rate = 1.0) {
    if (!('speechSynthesis' in window)) {
      if (isWeChatBrowser()) wechatFallbackAlert();
      return;
    }
    if (!text || !String(text).trim()) return;
    ns.stopSpeaking();
    const u = new SpeechSynthesisUtterance(String(text));
    u.lang = lang;
    u.rate = rate;
    const v = pickVoice(lang);
    if (v) u.voice = v;
    window.speechSynthesis.speak(u);
  };

  // Wraps each word in <span> for karaoke highlighting on `boundary` events.
  ns.speakElement = function (el, lang = 'en-GB', rate = 1.0) {
    if (!('speechSynthesis' in window)) {
      if (isWeChatBrowser()) wechatFallbackAlert();
      return;
    }
    if (!el) return;
    const text = el.textContent.trim();
    if (!text) return;

    // Re-wrap text in per-word spans so we can highlight by character offset.
    const tokens = text.split(/(\s+)/);
    el.innerHTML = '';
    const spans = [];
    const offsets = [];
    let charIdx = 0;
    tokens.forEach(tok => {
      if (/^\s+$/.test(tok)) {
        el.appendChild(document.createTextNode(tok));
      } else if (tok.length) {
        const s = document.createElement('span');
        s.textContent = tok;
        offsets.push({ span: s, start: charIdx, end: charIdx + tok.length });
        spans.push(s);
        el.appendChild(s);
      }
      charIdx += tok.length;
    });

    ns.stopSpeaking();
    _currentSpans = spans;

    const u = new SpeechSynthesisUtterance(text);
    u.lang = lang;
    u.rate = rate;
    const v = pickVoice(lang);
    if (v) u.voice = v;
    u.onboundary = function (ev) {
      if (ev.name && ev.name !== 'word') return;
      const idx = ev.charIndex;
      spans.forEach(s => s.classList.remove('speaking'));
      const hit = offsets.find(o => idx >= o.start && idx < o.end);
      if (hit) hit.span.classList.add('speaking');
    };
    u.onend = function () {
      spans.forEach(s => s.classList.remove('speaking'));
    };
    window.speechSynthesis.speak(u);
  };

  ns.speakElementById = function (id, lang = 'en-GB', rate = 1.0) {
    const el = document.getElementById(id);
    if (el) ns.speakElement(el, lang, rate);
  };

  // Voice list loads asynchronously on Chrome. Touching it here primes the cache
  // so the first user click already has voices available.
  if ('speechSynthesis' in window) {
    window.speechSynthesis.getVoices();
    window.speechSynthesis.onvoiceschanged = () => { /* lazy refresh on demand */ };
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (typeof ns.__init === 'function') ns.__init();
  });

})();
