/* === IELTS Interactive AI Correction — injected JS block === */
(function () {
  'use strict';

  // Substituted by make_interactive.py at build time.
  const AI_ENDPOINT = "__AI_ENDPOINT__";
  const PRONUNCIATIONS_URL = "__PRONUNCIATIONS_URL__";
  const LESSON_KEY = "__LESSON_KEY__"; // e.g. "Week_1_Lesson_Plan"

  const ns = (window.__ielts = window.__ielts || {});

  // Subsystems will register their public API on `ns` below.
  // See later sections in this file for: speakText, speakElementById,
  // stopSpeaking, correctEssay, editAgain, clearDraft, updateWordCount.

  document.addEventListener('DOMContentLoaded', () => {
    if (typeof ns.__init === 'function') ns.__init();
  });

})();
