/* CodeIQ client-side interactions.
 *
 * Almost everything here is a pure client-side toggle on markup that's
 * already fully rendered server-side (tabs, tooltips, more-info, snippet
 * expand, .md download) -- no Shiny round-trip needed. The one exception is
 * "view full file", which needs to read a file from disk, so it posts to a
 * Shiny input and a server-side effect opens the modal.
 *
 * Event delegation is used throughout since chat turns are added/replaced
 * dynamically by Shiny's render.ui.
 */
(function () {
  "use strict";

  function highlightAll(root) {
    if (window.Prism) {
      try {
        if (root && root.querySelectorAll) {
          Prism.highlightAllUnder(root);
        } else {
          Prism.highlightAll();
        }
      } catch (e) {
        /* noop -- a highlight glitch shouldn't break the app */
      }
    }
  }

  function scrollChatToBottom() {
    var panel = document.getElementById("chat-panel");
    if (panel) panel.scrollTop = panel.scrollHeight;
  }

  function closeAllPopovers(except) {
    document.querySelectorAll(".confidence-tag.tooltip-open").forEach(function (el) {
      if (el !== except) el.classList.remove("tooltip-open");
    });
    document.querySelectorAll(".more-info-wrap.open").forEach(function (el) {
      if (el !== except) el.classList.remove("open");
    });
  }

  function triggerDownload(filename, text) {
    var blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 1000);
  }

  document.addEventListener("click", function (e) {
    var infoDot = e.target.closest(".info-dot");
    if (infoDot) {
      var tag = infoDot.closest(".confidence-tag");
      var wasOpen = tag.classList.contains("tooltip-open");
      closeAllPopovers();
      if (!wasOpen) tag.classList.add("tooltip-open");
      e.stopPropagation();
      return;
    }

    var moreBtn = e.target.closest(".more-info-toggle");
    if (moreBtn) {
      var wrap = moreBtn.closest(".more-info-wrap");
      var wasOpenWrap = wrap.classList.contains("open");
      closeAllPopovers();
      if (!wasOpenWrap) wrap.classList.add("open");
      e.stopPropagation();
      return;
    }

    var tabBtn = e.target.closest(".tab-btn");
    if (tabBtn) {
      var nav = tabBtn.closest(".tabs-nav");
      var block = tabBtn.closest(".sources-block");
      if (nav && block) {
        nav.querySelectorAll(".tab-btn").forEach(function (b) {
          b.classList.remove("active");
        });
        tabBtn.classList.add("active");
        var targetId = tabBtn.getAttribute("data-tab");
        block.querySelectorAll(".tab-panel").forEach(function (p) {
          p.classList.toggle("active", p.id === targetId);
        });
        highlightAll(block.querySelector(".tab-panel.active"));
      }
      return;
    }

    var preview = e.target.closest(".code-preview");
    if (preview) {
      var wrapEl = preview.closest(".code-block-wrap");
      if (wrapEl) {
        wrapEl.classList.add("expanded");
        highlightAll(wrapEl);
      }
      return;
    }

    var collapseBtn = e.target.closest(".collapse-btn");
    if (collapseBtn) {
      var wrapEl2 = collapseBtn.closest(".code-block-wrap");
      if (wrapEl2) wrapEl2.classList.remove("expanded");
      return;
    }

    var copyBtn = e.target.closest(".copy-btn");
    if (copyBtn) {
      var codeEl = copyBtn.closest(".code-full").querySelector("code");
      if (codeEl && navigator.clipboard) {
        navigator.clipboard.writeText(codeEl.textContent || "").then(function () {
          var original = copyBtn.innerHTML;
          copyBtn.innerHTML = "\u2713 Copied";
          setTimeout(function () {
            copyBtn.innerHTML = original;
          }, 1200);
        });
      }
      return;
    }

    var viewFileBtn = e.target.closest(".view-full-file-btn");
    if (viewFileBtn) {
      var payload = {
        file: viewFileBtn.getAttribute("data-file"),
        start: parseInt(viewFileBtn.getAttribute("data-start"), 10) || 0,
        end: parseInt(viewFileBtn.getAttribute("data-end"), 10) || 0,
        _ts: Date.now(),
      };
      if (window.Shiny) {
        Shiny.setInputValue("codeiq_view_file", payload, { priority: "event" });
      }
      return;
    }

    var dlBtn = e.target.closest(".dl-btn");
    if (dlBtn) {
      var targetId = dlBtn.getAttribute("data-target");
      var ta = document.getElementById(targetId);
      if (ta) triggerDownload(dlBtn.getAttribute("data-filename") || "codeiq-export.md", ta.value);
      return;
    }

    var chip = e.target.closest(".example-chip");
    if (chip) {
      var input = document.getElementById("question");
      if (input) {
        input.value = chip.getAttribute("data-prompt") || chip.textContent.trim();
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.focus();
      }
      return;
    }

    if (!e.target.closest(".confidence-tag")) {
      document.querySelectorAll(".confidence-tag.tooltip-open").forEach(function (el) {
        el.classList.remove("tooltip-open");
      });
    }
    if (!e.target.closest(".more-info-wrap")) {
      document.querySelectorAll(".more-info-wrap.open").forEach(function (el) {
        el.classList.remove("open");
      });
    }
  });

  document.addEventListener("keydown", function (e) {
  if (e.key === "Enter" && !e.shiftKey && e.target && e.target.id === "question") {
    e.preventDefault();
    var btn = document.getElementById("send");
    if (btn && !btn.disabled) {
      Shiny.setInputValue("question", e.target.value, { priority: "event" });
      setTimeout(function () {
        btn.click();
      }, 0);
    }
  }
  if (e.key === "Escape") {
    closeAllPopovers();
  }
});

  window.codeiqHighlight = highlightAll;
  window.codeiqScrollToBottom = scrollChatToBottom;

  document.addEventListener("DOMContentLoaded", function () {
    highlightAll();
  });

  if (window.Shiny) {
    $(document).on("shiny:value", function (event) {
      if (event.name === "chat_output" || event.name === "composer_output") {
        setTimeout(function () {
          highlightAll(document.getElementById(event.name));
        }, 0);
      }
    });
  }
})();
