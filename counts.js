/* Fills the download counter on each slide from data/downloads.json.
 *
 * The number in that file is the sum of every GitHub release's APK downloads,
 * so it keeps counting across versions no matter which build a visitor took,
 * and it is committed to the repository, so editing the page never touches it.
 * If the file cannot be read the counter stays hidden rather than showing a
 * guess, and the slide still works exactly as it does without JavaScript.
 */
(function () {
  "use strict";

  var slots = document.querySelectorAll("[data-downloads]");
  if (!slots.length || typeof window.fetch !== "function" || !window.JSON) {
    return;
  }

  var format;
  try {
    format = new Intl.NumberFormat("en");
  } catch (error) {
    format = { format: function (value) { return String(value); } };
  }

  function paint(apps) {
    Array.prototype.forEach.call(slots, function (slot) {
      var entry = apps[slot.getAttribute("data-downloads")];
      var total = entry && entry.total;
      if (typeof total !== "number" || !isFinite(total) || total < 0) {
        return;
      }
      var value = slot.querySelector(".dl-count-value");
      if (value) {
        value.textContent = format.format(total);
      }
      slot.title = format.format(total) + " downloads so far, every version counted";
      slot.hidden = false;
    });
  }

  fetch("/data/downloads.json", { credentials: "same-origin", cache: "no-cache" })
    .then(function (response) {
      return response.ok ? response.json() : null;
    })
    .then(function (payload) {
      if (payload && payload.apps) {
        paint(payload.apps);
      }
    })
    .catch(function () {
      /* Leave every counter hidden: a missing number beats a wrong one. */
    });
})();
