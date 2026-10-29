/* Mobile swipe navigation for the app deck.
   Progressive enhancement only: without this file the top-bar arrows and the
   #app-01 / #app-02 fragments still move between slides, and the deck still
   works with JavaScript disabled. */
(function () {
  "use strict";

  // Phones and tablets: narrow viewports, or any coarse pointer such as a finger.
  // Keep this query in sync with the mobile swipe block in styles.css.
  var MOBILE_QUERY = "(max-width: 620px), (hover: none) and (pointer: coarse)";

  var ENGAGE_TRAVEL = 12; // px of horizontal travel before a drag becomes a swipe
  var COMMIT_RATIO = 0.2; // share of the deck width that commits a slide change
  var COMMIT_MIN = 52; // but never less than this many px
  var FLICK_VELOCITY = 0.4; // px per ms, so a quick flick commits regardless of distance
  var DRAG_LIMIT = 0.85; // the slide never trails further than this share of the deck

  var deck = document.querySelector(".deck");
  var stage = document.querySelector(".stage");
  if (!deck || !stage || !window.PointerEvent) {
    return;
  }

  var slides = Array.prototype.slice.call(deck.querySelectorAll(".slide"));
  if (slides.length < 2) {
    return;
  }

  var status = document.querySelector(".swipe-status");
  var mobile = window.matchMedia ? window.matchMedia(MOBILE_QUERY) : null;
  var drag = null;
  var blockClick = false;

  function isMobile() {
    return !mobile || mobile.matches;
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

  function slideWidth() {
    return deck.getBoundingClientRect().width || window.innerWidth || 320;
  }

  // Show the incoming slide from the edge the finger pushed toward, then let the
  // hash fragment take over visibility exactly as a nav tap would.
  function go(dir) {
    var from = currentIndex();
    var to = from + dir;
    if (to < 0 || to >= slides.length) {
      return false;
    }

    var incoming = slides[to];
    slides[from].classList.remove("swipe-in-next", "swipe-in-prev");
    incoming.classList.add(dir > 0 ? "swipe-in-next" : "swipe-in-prev");

    // Changing the fragment is exactly what a nav tap does, so visibility, the
    // active tab, and the arrow set stay owned by the existing CSS.
    window.location.hash = "#" + incoming.id;
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

  function resetSlide(slide) {
    slide.classList.remove("is-swiping");
    slide.style.removeProperty("--swipe-x");
    if (slide.getAttribute("style") === "") {
      // Leave no trace of the drag in the markup.
      slide.removeAttribute("style");
    }
  }

  function onPointerDown(event) {
    if (!isMobile() || drag || event.isPrimary === false) {
      return;
    }
    if (event.pointerType === "mouse" && event.button !== 0) {
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
      slide: slides[currentIndex()],
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
      drag.slide.classList.add("is-swiping");
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

    var limit = slideWidth() * DRAG_LIMIT;
    var offset = drag.x;
    if (!canGo(directionFor(offset))) {
      // Nothing to reach in that direction, so resist instead of sliding away.
      offset *= 0.28;
    }
    offset = Math.max(-limit, Math.min(limit, offset));
    drag.slide.style.setProperty("--swipe-x", offset.toFixed(1) + "px");
  }

  function onPointerUp(event) {
    if (!drag || event.pointerId !== drag.id) {
      return;
    }

    var gesture = drag;
    drag = null;
    resetSlide(gesture.slide);

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
    var width = slideWidth();
    var threshold = Math.min(width * 0.5, Math.max(COMMIT_MIN, width * COMMIT_RATIO));
    var flicked = Math.abs(gesture.velocity) >= FLICK_VELOCITY && Math.sign(gesture.velocity) === Math.sign(travelled);
    var far = Math.abs(travelled) >= threshold;

    if ((far || flicked) && Math.abs(travelled) > ENGAGE_TRAVEL) {
      // A committed swipe must not also open the link that sat under the finger.
      blockClick = true;
      window.setTimeout(function () {
        blockClick = false;
      }, 500);
      if (go(directionFor(travelled))) {
        return;
      }
    }
  }

  function onPointerCancel(event) {
    if (!drag || event.pointerId !== drag.id) {
      return;
    }
    resetSlide(drag.slide);
    drag = null;
  }

  function onClickCapture(event) {
    if (blockClick) {
      blockClick = false;
      event.preventDefault();
      event.stopPropagation();
    }
  }

  // The direction class only needs to live for the length of one entrance.
  deck.addEventListener("animationend", function (event) {
    if (event.animationName.indexOf("swipe-") !== 0) {
      return;
    }
    event.target.classList.remove("swipe-in-next", "swipe-in-prev");
  });

  stage.addEventListener("pointerdown", onPointerDown, { passive: true });
  stage.addEventListener("pointermove", onPointerMove, { passive: true });
  stage.addEventListener("pointerup", onPointerUp, { passive: true });
  stage.addEventListener("pointercancel", onPointerCancel, { passive: true });
  stage.addEventListener("click", onClickCapture, true);

  // Drag drift must never survive a resize or a rotation into desktop layout.
  window.addEventListener("resize", function () {
    if (!isMobile()) {
      slides.forEach(resetSlide);
      drag = null;
    }
  });
})();
