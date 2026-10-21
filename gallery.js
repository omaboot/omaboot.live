// The home page's test screens, larger (owner, 2026-10-21): a figure's screen, or a step's "Fig."
// link, opens it in a lightbox with its caption; ← and → (the buttons, the keys, a swipe) go
// through all of them, Esc or × closes. Without this script each screen is a plain link to its
// image, and a step's link jumps to its figure.
(function () {
  "use strict";
  var figs = Array.prototype.slice.call(document.querySelectorAll(".gallery figure"));
  if (!figs.length || typeof HTMLDialogElement === "undefined") return;

  var ns = "http://www.w3.org/2000/svg";
  function icon(d) {
    var svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    var path = document.createElementNS(ns, "path");
    path.setAttribute("d", d);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "currentColor");
    path.setAttribute("stroke-width", "1.6");
    path.setAttribute("stroke-linecap", "square");
    svg.appendChild(path);
    return svg;
  }
  function button(cls, label, d) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = cls;
    b.setAttribute("aria-label", label);
    b.appendChild(icon(d));
    return b;
  }

  var box = document.createElement("dialog");
  box.className = "lightbox";
  box.setAttribute("aria-label", "Test screens");
  var stage = document.createElement("div");
  stage.className = "lb-stage";
  var prev = button("lb-prev", "Previous screen", "M15 5l-7 7 7 7");
  var next = button("lb-next", "Next screen", "M9 5l7 7-7 7");
  var close = button("lb-close", "Close", "M5 5l14 14M19 5L5 19");
  var fig = document.createElement("figure");
  fig.className = "lb-fig";
  var img = document.createElement("img");
  var cap = document.createElement("figcaption");
  cap.className = "lb-cap";
  cap.setAttribute("aria-live", "polite");
  fig.appendChild(img);
  fig.appendChild(cap);
  stage.appendChild(prev);
  stage.appendChild(fig);
  stage.appendChild(next);
  box.appendChild(stage);
  box.appendChild(close);
  document.body.appendChild(box);

  var at = 0, opener = null;
  function show(i) {
    at = (i + figs.length) % figs.length;
    var src = figs[at].querySelector("img");
    img.src = src.currentSrc || src.src;
    img.alt = src.alt;
    // the caption as on the page, its "Fig. N" written out (the page draws it from a counter)
    cap.textContent = "";
    var text = figs[at].querySelector("figcaption").cloneNode(true);
    var title = text.querySelector("b");
    if (title) {
      title.setAttribute("data-fig", "Fig. " + (at + 1));
      var count = document.createElement("span");
      count.className = "lb-count";
      count.textContent = (at + 1) + " / " + figs.length;
      title.appendChild(count);
    }
    var p = document.createElement("p");
    while (text.firstChild) p.appendChild(text.firstChild);
    if (title) cap.appendChild(title);
    cap.appendChild(p);
    new Image().src = figs[(at + 1) % figs.length].querySelector("img").src; // the next one, ready
  }
  function open(i, from) {
    opener = from || null;
    show(i);
    document.documentElement.classList.add("lb-open");
    box.showModal();
    close.focus();
  }
  box.addEventListener("close", function () {
    document.documentElement.classList.remove("lb-open");
    if (opener) opener.focus();
  });

  prev.addEventListener("click", function () { show(at - 1); });
  next.addEventListener("click", function () { show(at + 1); });
  close.addEventListener("click", function () { box.close(); });
  box.addEventListener("keydown", function (e) {
    if (e.key === "ArrowLeft") { show(at - 1); e.preventDefault(); }
    else if (e.key === "ArrowRight") { show(at + 1); e.preventDefault(); }
  });
  // a click beside the screen and its caption closes, as Esc does
  stage.addEventListener("click", function (e) { if (e.target === stage) box.close(); });

  var x0 = null;
  box.addEventListener("pointerdown", function (e) { if (e.pointerType !== "mouse") x0 = e.clientX; });
  box.addEventListener("pointerup", function (e) {
    if (x0 === null) return;
    var dx = e.clientX - x0;
    x0 = null;
    if (Math.abs(dx) > 50) show(at + (dx < 0 ? 1 : -1));
  });

  figs.forEach(function (f, i) {
    var a = f.querySelector("a.shot");
    if (!a) return;
    a.addEventListener("click", function (e) {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return; // a new tab, as asked
      e.preventDefault();
      open(i, a);
    });
  });
  document.querySelectorAll("a.rail-fig").forEach(function (a) {
    var f = document.getElementById(a.hash.slice(1));
    var i = figs.indexOf(f);
    if (i < 0) return;
    a.addEventListener("click", function (e) {
      e.preventDefault();
      open(i, a);
    });
  });
})();
