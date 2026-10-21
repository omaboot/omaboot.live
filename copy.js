// omaboot.live's copy buttons, one on each command block (owner, 2026-10-16), as on
// DoesItOmarchy.com's Identify page. Blocks marked class="out" (what a command should print) get
// none. A block's data-copy names what it copies (the key fingerprints on Verify). Without this
// script the commands are plain text, still selectable.
(function () {
  "use strict";
  var status = document.createElement("p");
  status.className = "sr-only";
  status.setAttribute("aria-live", "polite");
  document.body.appendChild(status);

  function select(code) {
    var range = document.createRange();
    range.selectNodeContents(code);
    var sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
  }

  document.querySelectorAll("pre:not(.out) > code").forEach(function (code) {
    var pre = code.parentNode;
    var button = document.createElement("button");
    button.type = "button";
    button.className = "copy";
    button.textContent = "Copy";
    button.setAttribute("aria-label", pre.dataset.copy || "Copy the command" + (pre.dataset.label ? " for " + pre.dataset.label : ""));
    var timer;
    button.addEventListener("click", function () {
      var done = function (ok) {
        button.textContent = ok ? "Copied" : "Selected";
        status.textContent = ok ? "Copied to the clipboard." : "Selected: press Ctrl+C or Command+C to copy.";
        clearTimeout(timer);
        timer = setTimeout(function () { button.textContent = "Copy"; }, 1600);
      };
      var text = code.textContent.replace(/\n$/, "");
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(function () { done(true); }, function () { select(code); done(false); });
      } else {
        select(code);
        done(false);
      }
    });
    // the button sits on a wrapper, so it stays put when a long command scrolls
    var box = document.createElement("div");
    box.className = "codebox";
    pre.parentNode.insertBefore(box, pre);
    box.appendChild(pre);
    pre.classList.add("has-copy");
    box.appendChild(button);
  });
})();
