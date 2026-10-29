/* App 01 / App 02 deck: one screen at a time, with a staggered slide.
   Outgoing screen: text steps out, then the hairlines.
   Arriving screen: hairlines slide in, then the text.                     */
(function () {
  "use strict";

  var deck = document.querySelector("[data-deck]");
  if (!deck) {
    return;
  }

  var screens = Array.prototype.slice.call(deck.querySelectorAll(".screen"));
  if (screens.length < 2) {
    return;
  }

  var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  var SETTLE_MS = 1180;
  var current = 0;
  var busy = false;

  function isReduced() {
    return reducedMotion.matches;
  }

  function fromHash() {
    var match = /#app-(\d+)$/.exec(window.location.hash);
    if (!match) {
      return 0;
    }
    var next = Number(match[1]) - 1;
    return next >= 0 && next < screens.length ? next : 0;
  }

  function show(screen, booting) {
    screen.classList.remove("is-parked", "is-leaving", "is-entering");
    if (booting) {
      screen.classList.add("is-booting");
    }
    screen.inert = false;
    screen.removeAttribute("aria-hidden");
  }

  function park(screen) {
    screen.classList.remove("is-active", "is-booting", "is-entering", "is-leaving");
    screen.classList.add("is-parked");
    screen.inert = true;
    screen.setAttribute("aria-hidden", "true");
  }

  function writeHash(index) {
    if (!window.history || !window.history.replaceState) {
      return;
    }
    try {
      window.history.replaceState(null, "", "#" + screens[index].id);
    } catch (error) {
      /* file:// and sandboxed frames can refuse this; the deck still works. */
    }
  }

  function focusInside(element) {
    var target = element.querySelector(".nav");
    if (target) {
      target.focus({ preventScroll: true });
    }
  }

  function go(target, direction) {
    if (busy) {
      return;
    }
    var next = Number(target);
    if (!Number.isInteger(next) || next < 0 || next >= screens.length || next === current) {
      return;
    }

    busy = true;
    deck.setAttribute("data-dir", direction || (next > current ? "forward" : "back"));

    var leaving = screens[current];
    var arriving = screens[next];
    var focusWasInside = leaving.contains(document.activeElement);

    // Drop any boot-in animation so the slide-out styles take over cleanly.
    leaving.classList.remove("is-active", "is-booting", "is-entering");
    arriving.classList.remove("is-booting");
    leaving.classList.add("is-leaving");
    leaving.setAttribute("aria-hidden", "true");

    show(arriving, false);
    arriving.classList.add("is-active", "is-entering");

    current = next;
    writeHash(next);

    if (focusWasInside) {
      focusInside(arriving);
    }
    leaving.inert = true;

    window.setTimeout(function () {
      park(leaving);
      arriving.classList.remove("is-entering");
      busy = false;
    }, isReduced() ? 60 : SETTLE_MS);
  }

  deck.addEventListener("click", function (event) {
    var trigger = event.target.closest("[data-goto]");
    if (!trigger) {
      return;
    }
    event.preventDefault();
    go(trigger.getAttribute("data-goto"));
  });

  document.addEventListener("keydown", function (event) {
    if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) {
      return;
    }
    if (event.key === "ArrowRight") {
      go(Math.min(current + 1, screens.length - 1), "forward");
    } else if (event.key === "ArrowLeft") {
      go(Math.max(current - 1, 0), "back");
    }
  });

  window.addEventListener("hashchange", function () {
    go(fromHash());
  });

  // Land on the screen named in the URL, if any.
  var start = fromHash();
  screens.forEach(function (screen, index) {
    if (index === start) {
      screen.classList.add("is-active");
      screen.inert = false;
      screen.removeAttribute("aria-hidden");
      return;
    }
    park(screen);
  });
  current = start;
  writeHash(start);

  // The boot-in animation only plays once.
  window.setTimeout(function () {
    screens.forEach(function (screen) {
      screen.classList.remove("is-booting");
    });
  }, 1400);
})();
