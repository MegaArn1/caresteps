/* CareSteps client script.
 *
 * Deliberately small and dependency-free. Three jobs:
 *   1. the conversational panel (fetch, render, option buttons)
 *   2. the trend chart, which must BREAK at a gap rather than draw across it
 *   3. modest affordances: double-submit guard, composer autosize
 *
 * Nothing here makes a clinical decision. The chart plots exactly what the server
 * computed and reports the same counts the server reported.
 */

(function () {
  "use strict";

  /* ------------------------------------------------------- double-submit guard
   * A repeated tap on Save must not create two records. The server is idempotent
   * anyway (dedupe_key), but disabling the button gives the user immediate feedback
   * instead of a silent no-op.
   */
  document.querySelectorAll("form[data-guard]").forEach(function (form) {
    form.addEventListener("submit", function () {
      var btn = form.querySelector("button[type=submit], button:not([type])");
      if (!btn) return;
      setTimeout(function () {
        btn.disabled = true;
        btn.dataset.originalText = btn.textContent;
        btn.textContent = "Saving…";
      }, 0);
    });
  });

  /* ------------------------------------------------------------ chat composer */

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function renderReply(target, data) {
    var wrap = el("div", "msg assistant");

    // Emergency replies get a completely different treatment: solid red, prominent,
    // and nothing else competing with it on the screen.
    if (data.mode === "safety" && (data.payload.kind === "emergency" || data.payload.kind === "urgent")) {
      wrap = el("div", "msg emergency");
      var h = el("p", null, data.text);
      h.style.fontWeight = "700";
      h.style.fontSize = "20px";
      wrap.appendChild(h);

      var help = data.payload.help || {};
      if (help.number) {
        var num = el("p");
        var link = el("a", null, help.label + ": " + help.number);
        link.href = "tel:" + help.number;
        link.style.color = "#fff";
        link.style.fontWeight = "700";
        link.style.fontSize = "26px";
        num.appendChild(link);
        wrap.appendChild(num);
      }
      if (help.app_does_not) {
        var warn = el("p", "small", help.app_does_not);
        wrap.appendChild(warn);
      }
      // The routine flow stays reachable; an emergency message must not strand
      // someone who has already started recording something.
      if (data.payload.can_still_record) {
        var cont = el("p", "small", "You can still save a reading if you were in the middle of one.");
        wrap.appendChild(cont);
      }
      target.appendChild(wrap);
      return;
    }

    if (data.mode === "safety") wrap.className = "msg safety";

    wrap.appendChild(el("p", null, data.text));

    // Option buttons from a clarification or a barrier question.
    var options = (data.payload && data.payload.options) || [];
    if (options.length) {
      var choices = el("div", "choices");
      options.forEach(function (opt) {
        var b = el("button", null, opt.label);
        b.type = "button";
        b.addEventListener("click", function () {
          sendMessage(opt.label);
        });
        choices.appendChild(b);
      });
      wrap.appendChild(choices);
    }

    // A reading or medication draft that the assistant prepared needs a confirm
    // button. The draft_id is echoed from the server so we can POST it back
    // without the user navigating away.
    var draftId = data.payload && data.payload.draft_id;
    var needsConfirm = data.payload && data.payload.needs_confirmation && draftId;
    if (needsConfirm) {
      var kind = data.payload.kind; // "reading_draft" | "medication_draft"
      var label = kind === "reading_draft" ? "Save this reading" : "Confirm medication record";
      var confirmBtn = el("button", "btn", label);
      confirmBtn.type = "button";
      confirmBtn.style.marginTop = "10px";
      confirmBtn.addEventListener("click", function () {
        confirmBtn.disabled = true;
        confirmBtn.textContent = "Saving…";
        fetch("/api/chat/confirm", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: "draft_id=" + encodeURIComponent(draftId)
        })
          .then(function (r) { return r.json(); })
          .then(function (res) {
            if (res.ok) {
              confirmBtn.textContent = "Saved ✓";
            } else {
              confirmBtn.textContent = "Could not save — please try again";
              confirmBtn.disabled = false;
            }
          })
          .catch(function () {
            confirmBtn.textContent = "Could not reach the app — try again";
            confirmBtn.disabled = false;
          });
      });
      wrap.appendChild(confirmBtn);
    }

    // A boundary refusal offers the constructive route rather than dead-ending.
    if (data.payload && data.payload.offer_add_question) {
      var qbtn = el("button", "btn ghost", "Add this to my questions for the doctor");
      qbtn.type = "button";
      qbtn.style.marginTop = "10px";
      qbtn.addEventListener("click", function () {
        var text = data.payload.suggest_question || "I would like to ask about this at my next appointment.";
        fetch("/summary/question/add", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: "text=" + encodeURIComponent(text) + "&origin=safety"
        }).then(function () {
          qbtn.textContent = "Added to your questions";
          qbtn.disabled = true;
        });
      });
      wrap.appendChild(qbtn);
    }

    // Source attribution, shown for anything that explained a medicine.
    if (data.sources && data.sources.length && data.tool_calls) {
      var srcCall = data.tool_calls.filter(function (c) { return c.name === "retrieve_education"; })[0];
      if (srcCall) {
        var meta = el("span", "meta", "Answered from a recorded source. See the trace page for detail.");
        wrap.appendChild(meta);
      }
    }

    // Every assistant turn states which mode produced it. This is the honesty
    // requirement made visible at the point of use.
    var badge = el("span", "meta",
      data.agent_mode === "degraded" ? "Answered by the simple rule set (no model connected)"
      : data.agent_mode === "safety" ? "Answered by the safety rules"
      : "Answered by the assistant");
    if (data.agent_mode === "live" && data.latency_ms) {
      badge.textContent += " · " + (data.latency_ms / 1000).toFixed(1) + "s";
    }
    wrap.appendChild(badge);

    target.appendChild(wrap);
  }

  function sendMessage(text) {
    var log = document.getElementById("chat-log");
    var input = document.getElementById("chat-input");
    if (!log) return;

    log.appendChild(el("div", "msg user", text));
    if (input) input.value = "";
    log.scrollTop = log.scrollHeight;

    var pending = el("div", "msg assistant", "…");
    pending.id = "chat-pending";
    log.appendChild(pending);
    log.scrollTop = log.scrollHeight;

    fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "message=" + encodeURIComponent(text)
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var p = document.getElementById("chat-pending");
        if (p) p.remove();
        if (!data.ok) {
          log.appendChild(el("div", "msg safety", data.error || "Something went wrong. Nothing was saved."));
          return;
        }
        renderReply(log, data);
        log.scrollTop = log.scrollHeight;
      })
      .catch(function () {
        var p = document.getElementById("chat-pending");
        if (p) p.remove();
        // A failed request must not look like a successful one.
        log.appendChild(el("div", "msg safety",
          "I could not reach the app just now, so nothing was saved. Please try again."));
      });
  }

  var form = document.getElementById("chat-form");
  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var input = document.getElementById("chat-input");
      var text = (input.value || "").trim();
      if (text) sendMessage(text);
    });

    var ta = document.getElementById("chat-input");
    if (ta) {
      ta.addEventListener("input", function () {
        ta.style.height = "auto";
        ta.style.height = Math.min(ta.scrollHeight, 160) + "px";
      });
    }
  }

  // Exposed so inline option buttons elsewhere can drive the same flow.
  window.carestepsChat = sendMessage;

  /* ----------------------------------------------------------- demo reset button */

  var resetBtn = document.getElementById("reset-demo-btn");
  if (resetBtn) {
    resetBtn.addEventListener("click", function () {
      if (!confirm("Reset all demo data? This will remove any changes you made and restore the fictional demo patient.")) {
        return;
      }

      resetBtn.disabled = true;
      resetBtn.textContent = "Resetting...";

      fetch("/api/demo/reset", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" }
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.ok) {
            resetBtn.textContent = "Reset complete ✓";
            setTimeout(function () {
              window.location.href = "/app";
            }, 1000);
          } else {
            resetBtn.textContent = "Reset failed";
            resetBtn.disabled = false;
            alert(data.error || "Could not reset demo data. Please try again.");
          }
        })
        .catch(function () {
          resetBtn.textContent = "Reset demo data";
          resetBtn.disabled = false;
          alert("Could not reach the server. Please try again.");
        });
    });
  }

  /* ------------------------------------------------------------------- chart
   * Renders from the `series` the server produced. The important behaviour is that a
   * day with no data produces a BREAK, not a line straight across it - which is the
   * difference between showing a gap and hiding one.
   */
  function drawChart(svg, series) {
    if (!svg || !series || !series.length) return;

    var NS = "http://www.w3.org/2000/svg";
    var W = 640, H = 240, PAD = { t: 16, r: 12, b: 34, l: 44 };
    var pw = W - PAD.l - PAD.r;
    var ph = H - PAD.t - PAD.b;

    var ys = series.filter(function (p) { return p.has_data; });
    if (!ys.length) return;

    var vals = [];
    ys.forEach(function (p) { vals.push(p.systolic, p.diastolic); });
    var lo = Math.min.apply(null, vals) - 10;
    var hi = Math.max.apply(null, vals) + 10;
    lo = Math.floor(lo / 10) * 10;
    hi = Math.ceil(hi / 10) * 10;

    function x(i) { return PAD.l + (series.length === 1 ? pw / 2 : (i / (series.length - 1)) * pw); }
    function y(v) { return PAD.t + ph - ((v - lo) / (hi - lo)) * ph; }

    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    svg.setAttribute("role", "img");

    // A textual description for screen readers, built from the same numbers.
    svg.setAttribute("aria-label",
      "Blood pressure chart. " + ys.length + " of " + series.length +
      " days have readings. Values range from " + lo + " to " + hi + " millimetres of mercury.");

    function mk(tag, attrs) {
      var n = document.createElementNS(NS, tag);
      for (var k in attrs) n.setAttribute(k, attrs[k]);
      return n;
    }

    // Horizontal gridlines with labels.
    for (var g = lo; g <= hi; g += 20) {
      svg.appendChild(mk("line", { class: "grid", x1: PAD.l, y1: y(g), x2: W - PAD.r, y2: y(g) }));
      var t = mk("text", { x: PAD.l - 8, y: y(g) + 4, "text-anchor": "end" });
      t.textContent = g;
      svg.appendChild(t);
    }

    // Axes.
    svg.appendChild(mk("line", { class: "axis", x1: PAD.l, y1: PAD.t, x2: PAD.l, y2: PAD.t + ph }));
    svg.appendChild(mk("line", { class: "axis", x1: PAD.l, y1: PAD.t + ph, x2: W - PAD.r, y2: PAD.t + ph }));

    // Date labels, thinned so they do not crowd.
    var step = Math.ceil(series.length / 6);
    series.forEach(function (p, i) {
      if (i % step !== 0 && i !== series.length - 1) return;
      var tx = mk("text", { x: x(i), y: H - 12, "text-anchor": "middle" });
      tx.textContent = p.date.slice(5); // MM-DD
      svg.appendChild(tx);
    });

    // Draw each contiguous run of days-with-data as its own path, so a gap creates a
    // break. This is the whole point of the function.
    function runsFor(key) {
      var runs = [], cur = [];
      series.forEach(function (p, i) {
        if (p.has_data) {
          cur.push([x(i), y(p[key]), i, p]);
        } else if (cur.length) {
          runs.push(cur); cur = [];
        }
      });
      if (cur.length) runs.push(cur);
      return runs;
    }

    ["systolic", "diastolic"].forEach(function (key) {
      runsFor(key).forEach(function (run) {
        if (run.length === 1) {
          var only = run[0];
          svg.appendChild(mk("circle", {
            class: "pt" + (key === "diastolic" ? " dia" : "") +
                   (only[3].had_correction ? " revised" : ""),
            cx: only[0], cy: only[1], r: 4.5
          }));
          return;
        }
        var d = run.map(function (pt, i) { return (i ? "L" : "M") + pt[0].toFixed(1) + " " + pt[1].toFixed(1); }).join(" ");
        svg.appendChild(mk("path", {
          class: "series" + (key === "diastolic" ? " dia" : ""),
          d: d
        }));
        run.forEach(function (pt) {
          var point = pt[3];
          svg.appendChild(mk("circle", {
            class: "pt" + (key === "diastolic" ? " dia" : "") +
                   (point.had_correction ? " revised" : ""),
            cx: pt[0], cy: pt[1], r: point.had_correction ? 5 : 3.5
          }));
        });
      });
    });

    // Mark the gaps explicitly, so they are visible as information rather than as
    // empty space the eye reads as "fine".
    var gapStart = null;
    series.forEach(function (p, i) {
      if (!p.has_data && gapStart === null) gapStart = i;
      if (p.has_data && gapStart !== null) {
        var mid = (x(gapStart - 1) + x(i)) / 2;
        svg.appendChild(mk("line", { class: "gap", x1: mid, y1: PAD.t + 6, x2: mid, y2: PAD.t + ph - 6 }));
        gapStart = null;
      }
    });
  }

  document.querySelectorAll("svg[data-series]").forEach(function (svg) {
    try {
      drawChart(svg, JSON.parse(svg.getAttribute("data-series")));
    } catch (e) {
      // A chart that fails to draw must say so rather than render as a blank box.
      svg.outerHTML = '<p class="muted small">The chart could not be drawn. The numbers above are the same data.</p>';
    }
  });
})();
