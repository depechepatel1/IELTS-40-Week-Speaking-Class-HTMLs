// 01_state.js - shared closure-state for all later modules.
// Every later module reads these via the IIFE closure (no import).
// Carved from original inserted_script.js: ALL `const`/`let`
// declarations at IIFE scope, in original textual order.

  const FEMALE_NEURAL_UK = /Sonia|Libby|Mia|Maisie|Kate|Serena|Sienna|Tessa|Karen|Hazel|Susan|Stephanie/i;
  const MALE_NEURAL_UK   = /Ryan|Thomas.*GB|Christopher|Noah|Daniel|George|Oliver/i;
  const FEMALE_NEURAL_US = /Aria|Jenny|Ana|Michelle|Emma|Samantha|Allison|Ava|Joanna|Salli|Kendra|Kimberly|Ivy|Nora|Susan.*US|Zira|Helena|Heather/i;
  const MALE_NEURAL_US   = /Christopher|Guy|Tony|Jason|Eric|Davis|Alex|Aaron|Brandon|Steffan|Roger|David\b|Mark\b|Paul\b|James\b/i;
  const IOS_PREMIUM_NAMES =
    /Ava|Aaron|Nicky|Evan|Joelle|Noelle|Zoe|Catherine|Serena|Stephanie|Daniel|Arthur|Oliver|Martha/i;
  const FEMALE_NEURAL_ANY = new RegExp(
    FEMALE_NEURAL_UK.source + "|" + FEMALE_NEURAL_US.source, "i"
  );
  const MALE_NEURAL_ANY = new RegExp(
    MALE_NEURAL_UK.source + "|" + MALE_NEURAL_US.source, "i"
  );
  const _voiceCache = new Map();
  const DEFAULT_RATE = 0.85;
  const SLOW_RATE    = 0.72;
  // Round 53 — consolidated user preferences. Replaces the 3 separate
  // _userPreferred* globals. Read sites in other modules now use _prefs.lang,
  // _prefs.gender, _prefs.slow. The original Round-31/33/39 historical
  // comment blocks remain in 03_tts_voice.js where they were carved.
  const _prefs = {
    lang: 'en-GB',      // 'en-GB' | 'en-US' — sticky teaching accent (set by speakElement)
    gender: 'female',   // 'female' | 'male' — sticky teaching gender (set by gender toggle)
    slow: false,        // true = play every utterance at SLOW_RATE; toggled by 🐢 button
  };
  let _ttsWarmedUp = false;
  const AI_FETCH_MAX_ATTEMPTS = 3;
  const AI_FETCH_BASE_BACKOFF_MS = 1000;
  const AI_FETCH_JITTER_MS = 500;
  const AI_FETCH_TIMEOUT_MS = 45000;
  const _rowState = new WeakMap();
  let   _currentRow = null;
  const INLINE_GLOSS_RE = /\([^()]*[一-鿿㐀-䶿][^()]*\)|[一-鿿㐀-䶿　-〿＀-￯]+/g;
  const _wordWrapCache = new WeakMap();
  const STORAGE_KEY = `ielts:draft:${LESSON_KEY}`;
  let _saveTimer = null;
  const WORD_CLICK_SCOPE =
    '.model-box, .sec-4 .item-text, .sec-10 .item-text, ' +
    '.section-prompt-and-model > p:not(.model-box), .q-prompt';
  let _pronunciationsCache = null;
  const VR_DB_NAME    = /igcse/i.test(window.location.hostname || '')
                          ? 'igcse-recordings'
                          : 'ielts-recordings';
  const VR_STORE      = 'recordings';
  const VR_MAX_MS     = 3 * 60 * 1000;
  let _vrMediaRecorder = null;
  let _vrChunks        = [];
  let _vrStartedAt     = 0;
  let _vrPausedTotal   = 0;
  let _vrPausedAt      = 0;
  let _vrTimerId       = 0;
  let _vrStream        = null;
  let _activeContainer = null;
  let _vrStopPromise   = null;
  const _vrSavedBlobUrls = new WeakMap();
  const VR_MAX_RECORDINGS = 60;          // hard cap — never exceed this regardless of free quota
  const VR_QUOTA_HEADROOM = 0.20;        // start evicting when free quota < 20% of usable
  let _vrPersistRequested = false;
  const _EMAIL_LS_KEY = 'lessonEmailRecipient';
  const _EMAIL_VALID_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  let _crcTable = null;
