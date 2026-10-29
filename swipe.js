/* Mobile swipe navigation for the app deck.
   Progressive enhancement only: only the middle (.core) elements respond to and
   move with the gesture while the top bar, bottom bar, and hairlines remain
   stationary. Without this file the top-bar arrows and the #app-01 / #app-02 /
   #app-03 fragments still move between slides. */
(function () {
  "use strict";

  // Phones and tablets: narrow viewports, or any coarse pointer such as a finger.
  // Keep this query in sync with the mobile swipe block in styles.css.
  var MOBILE_QUERY = "(max-width: 620px), (hover: none) and (pointer: coarse)";
  var REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

  var ENGAGE_TRAVEL = 12; // px of horizontal travel before a drag becomes a swipe
  var COMMIT_RATIO = 0.2; // share of the middle width that commits a slide change
  var COMMIT_MIN = 52; // but never less than this many px
  var FLICK_VELOCITY = 0.4; // px per ms, so a quick flick commits regardless of distance
  var DRAG_LIMIT = 0.85; // the middle group never trails further than this share of the width
  var SNAP_MS = 220; // fallback cleanup window for an uncommitted snap-back

  var deck = document.querySelector(".deck");
  var stage = document.querySelector(".stage");
  if (!deck || !stage || !window.PointerEvent) {
    return;
  }

  var slides = Array.prototype.slice.call(deck.querySelectorAll(".slide"));
  var cores = slides.map(function (slide) {
    return slide.querySelector(".core");
  });
  if (slides.length < 2 || cores.some(function (core) { return !core; })) {
    return;
  }

  var status = document.querySelector(".swipe-status");
  var mobile = window.matchMedia ? window.matchMedia(MOBILE_QUERY) : null;
  var reducedMotion = window.matchMedia ? window.matchMedia(REDUCED_MOTION_QUERY) : null;
  var drag = null;
  var blockClick = false;
  var lastSwipeHash = "";
  var snapTimer = 0;

  if (!window.location.hash) {
    // Slide 01 is already on screen at /, so tapping 01 (#app-01) must not re-enter.
    cores[0].classList.add("is-settled");
  }

  function isMobile() {
    return !mobile || mobile.matches;
  }

  function prefersReducedMotion() {
    return Boolean(reducedMotion && reducedMotion.matches);
  }

  function currentIndex() {
    var hash = window.location.hash;
    for (var i = 0; i < slides.length; i += 1) {
      if (hash === "#" + slides[i].id) {
        return i;
      }
    }
    return 0;
  }

  function directionFor(dx) {
    // A leftward drag (negative dx) walks forward through the deck.
    return dx < 0 ? 1 : -1;
  }

  function canGo(dir) {
    var next = currentIndex() + dir;
    return next >= 0 && next < slides.length;
  }

  function coreWidth() {
    var active = cores[currentIndex()];
    return (active && active.getBoundingClientRect().width) || deck.getBoundingClientRect().width || window.innerWidth || 320;
  }

  function clearSnapTimer() {
    if (snapTimer) {
      window.clearTimeout(snapTimer);
      snapTimer = 0;
    }
  }

  function resetCore(core) {
    if (!core) {
      return;
    }
    core.classList.remove("is-swiping", "is-snapping");
    core.style.removeProperty("--swipe-x");
    if (core.getAttribute("style") === "") {
      // Leave no trace of the drag in the markup.
      core.removeAttribute("style");
    }
  }

  function snapBack(core) {
    if (!core) {
      return;
    }
    clearSnapTimer();
    if (prefersReducedMotion()) {
      resetCore(core);
      return;
    }
    core.classList.add("is-snapping");
    core.classList.remove("is-swiping");
    core.style.removeProperty("--swipe-x");
    if (core.getAttribute("style") === "") {
      core.removeAttribute("style");
    }
    snapTimer = window.setTimeout(function () {
      snapTimer = 0;
      core.classList.remove("is-snapping");
    }, SNAP_MS);
  }

  // Bring the incoming middle elements in from the edge the finger pushed toward,
  // while keeping the top bar, bottom bar, and hairlines completely untouched.
  function go(dir) {
    var from = currentIndex();
    var to = from + dir;
    if (to < 0 || to >= slides.length) {
      return false;
    }

    var outgoingCore = cores[from];
    var incoming = slides[to];
    var incomingCore = cores[to];

    deck.classList.add("has-interacted");
    clearSnapTimer();

    // Mark the incoming middle group settled BEFORE changing the fragment so
    // :target never starts a competing entrance or restarts one on animationend.
    resetCore(incomingCore);
    incomingCore.classList.remove("swipe-in-next", "swipe-in-prev");
    incomingCore.classList.add("is-settled", dir > 0 ? "swipe-in-next" : "swipe-in-prev");

    var scrollX = window.scrollX || window.pageXOffset || 0;
    var scrollY = window.scrollY || window.pageYOffset || 0;
    lastSwipeHash = "#" + incoming.id;

    // Changing the fragment is exactly what a nav tap does, so visibility, the
    // active tab, and the arrow set stay owned by the existing CSS.
    window.location.hash = "#" + incoming.id;
    if ((window.scrollX || 0) !== scrollX || (window.scrollY || 0) !== scrollY) {
      window.scrollTo(scrollX, scrollY);
    }

    // Reset the outgoing middle group only after the fragment change hid its slide.
    resetCore(outgoingCore);
    outgoingCore.classList.remove("swipe-in-next", "swipe-in-prev", "is-settled");

    announce(to);
    return true;
  }

  function announce(index) {
    if (!status) {
      return;
    }
    var heading = slides[index].querySelector(".app-code");
    var label = heading ? heading.textContent.replace(/\s+/g, " ").trim() : "";
    status.textContent = "App " + (index + 1) + " of " + slides.length + (label ? ": " + label : "");
  }

  function isInMiddleBand(event, activeCore) {
    var target = event.target;
    if (target && target.closest && target.closest(".bar")) {
      return false;
    }
    if (target && activeCore.contains(target)) {
      return true;
    }
    var rect = activeCore.getBoundingClientRect();
    if (rect.height > 0 && (event.clientY < rect.top || event.clientY > rect.bottom)) {
      return false;
    }
    return true;
  }

  function onPointerDown(event) {
    if (!isMobile() || drag || event.isPrimary === false) {
      return;
    }
    if (event.pointerType === "mouse" && event.button !== 0) {
      return;
    }

    var activeCore = cores[currentIndex()];
    if (!activeCore || !isInMiddleBand(event, activeCore)) {
      return;
    }

    drag = {
      id: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      x: 0,
      y: 0,
      lastX: event.clientX,
      lastTime: event.timeStamp || Date.now(),
      velocity: 0,
      engaged: false,
      core: activeCore,
    };
  }

  function onPointerMove(event) {
    if (!drag || event.pointerId !== drag.id) {
      return;
    }

    drag.x = event.clientX - drag.startX;
    drag.y = event.clientY - drag.startY;

    if (!drag.engaged) {
      // Hand a mostly vertical gesture back to the browser so the page still scrolls.
      if (Math.abs(drag.y) > ENGAGE_TRAVEL && Math.abs(drag.y) > Math.abs(drag.x)) {
        drag = null;
        return;
      }
      if (Math.abs(drag.x) < ENGAGE_TRAVEL || Math.abs(drag.x) <= Math.abs(drag.y)) {
        return;
      }
      drag.engaged = true;
      clearSnapTimer();
      deck.classList.add("has-interacted");
      drag.core.classList.remove("is-snapping", "swipe-in-next", "swipe-in-prev");
      drag.core.classList.add("is-settled", "is-swiping");
      if (stage.setPointerCapture) {
        try {
          stage.setPointerCapture(event.pointerId);
        } catch (error) {
          /* Capture is a nicety; the gesture still works without it. */
        }
      }
    }

    var now = event.timeStamp || Date.now();
    var elapsed = now - drag.lastTime;
    if (elapsed > 0) {
      drag.velocity = (event.clientX - drag.lastX) / elapsed;
    }
    drag.lastX = event.clientX;
    drag.lastTime = now;

    var limit = coreWidth() * DRAG_LIMIT;
    var offset = drag.x;
    if (!canGo(directionFor(offset))) {
      // Nothing to reach in that direction, so resist instead of sliding away.
      offset *= 0.28;
    }
    offset = Math.max(-limit, Math.min(limit, offset));
    drag.core.style.setProperty("--swipe-x", offset.toFixed(1) + "px");
  }

  function onPointerUp(event) {
    if (!drag || event.pointerId !== drag.id) {
      return;
    }

    var gesture = drag;
    drag = null;

    if (!gesture.engaged) {
      return;
    }

    if (stage.releasePointerCapture) {
      try {
        stage.releasePointerCapture(event.pointerId);
      } catch (error) {
        /* Already released. */
      }
    }

    var travelled = gesture.x;
    var width = coreWidth();
    var threshold = Math.min(width * 0.5, Math.max(COMMIT_MIN, width * COMMIT_RATIO));
    var flicked = Math.abs(gesture.velocity) >= FLICK_VELOCITY && Math.sign(gesture.velocity) === Math.sign(travelled);
    var far = Math.abs(travelled) >= threshold;

    if ((far || flicked) && Math.abs(travelled) > ENGAGE_TRAVEL) {
      var dir = directionFor(travelled);
      if (canGo(dir)) {
        // A committed swipe must not also open the link that sat under the finger.
        blockClick = true;
        window.setTimeout(function () {
          blockClick = false;
        }, 500);
        if (go(dir)) {
          return;
        }
      }
    }

    snapBack(gesture.core);
  }

  function onPointerCancel(event) {
    if (!drag || event.pointerId !== drag.id) {
      return;
    }
    var gesture = drag;
    drag = null;
    if (gesture.engaged) {
      snapBack(gesture.core);
    }
  }

  function onClickCapture(event) {
    if (blockClick) {
      blockClick = false;
      event.preventDefault();
      event.stopPropagation();
    }
  }

  // Keep .is-settled after animations end so :target never replays and flickers.
  deck.addEventListener("animationend", function (event) {
    var target = event.target;
    if (!target || !target.classList || !target.classList.contains("core")) {
      return;
    }
    if (event.animationName.indexOf("swipe-") === 0) {
      target.classList.add("is-settled");
      target.classList.remove("swipe-in-next", "swipe-in-prev");
    } else if (event.animationName === "slide-in") {
      target.classList.add("is-settled");
    }
  });

  deck.addEventListener("transitionend", function (event) {
    var target = event.target;
    if (target && target.classList && target.classList.contains("is-snapping")) {
      clearSnapTimer();
      target.classList.remove("is-snapping");
    }
  });

  window.addEventListener("hashchange", function () {
    deck.classList.add("has-interacted");
    var active = currentIndex();
    var fromSwipe = window.location.hash === lastSwipeHash;
    lastSwipeHash = "";
    cores.forEach(function (core, index) {
      if (index !== active) {
        resetCore(core);
        core.classList.remove("swipe-in-next", "swipe-in-prev", "is-settled");
      } else if (!fromSwipe) {
        resetCore(core);
        core.classList.remove("swipe-in-next", "swipe-in-prev");
      }
    });
  });

  stage.addEventListener("pointerdown", onPointerDown, { passive: true });
  stage.addEventListener("pointermove", onPointerMove, { passive: true });
  stage.addEventListener("pointerup", onPointerUp, { passive: true });
  stage.addEventListener("pointercancel", onPointerCancel, { passive: true });
  stage.addEventListener("click", onClickCapture, true);

  // Drag drift must never survive a resize or a rotation into desktop layout.
  window.addEventListener("resize", function () {
    if (!isMobile()) {
      clearSnapTimer();
      cores.forEach(resetCore);
      drag = null;
    }
  });
})();
