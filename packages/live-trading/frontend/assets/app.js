/* War Room frontend: ambil fragmen backend, suntik ke halaman, jalankan scriptnya. */
"use strict";

function jam() {
  var el = document.getElementById("t-jam");
  if (!el) return;
  try {
    el.textContent = new Date().toLocaleTimeString("id-ID", { hour12: false, timeZone: "Asia/Jakarta" }) + " WIB";
  } catch (e) { /* jam opsional */ }
}

function tandaiNav() {
  var p = location.pathname.replace(/\/$/, "") || "/";
  var links = document.querySelectorAll(".topbar a.nav[href]");
  for (var i = 0; i < links.length; i++) {
    var h = links[i].getAttribute("href");
    if (h === p || (h !== "/" && p.indexOf(h) === 0)) links[i].setAttribute("aria-current", "page");
  }
}

function jalankanScriptwadah(wadah) {
  wadah.querySelectorAll("script").forEach(function (lama) {
    var baru = document.createElement("script");
    if (lama.src) {
      baru.src = lama.src;
    } else {
      baru.textContent = lama.textContent;
    }
    lama.replaceWith(baru);
  });
}

async function muatFragmen() {
  var daftar = document.querySelectorAll("[data-frag]");
  for (const el of daftar) {
    var nama = el.getAttribute("data-frag");
    var html = null;
    for (var coba = 0; coba < 3 && html === null; coba++) {
      try {
        if (coba > 0) await new Promise(function (t) { setTimeout(t, 2000 * coba); });
        var r = await fetch("/frag/" + nama, { cache: "no-store" });
        if (!r.ok) throw new Error("http " + r.status);
        html = await r.text();
      } catch (e) {
        if (coba === 2) throw e;
      }
    }
    try {
      if (html === null) throw new Error("kosong");
      if (!html.trim()) {
        el.remove();
        continue;
      }
      el.innerHTML = html;
      jalankanScriptwadah(el);
    } catch (e) {
      el.innerHTML = "<p class='err'>gagal muat " + nama + "</p>";
    }
  }
}

document.addEventListener("DOMContentLoaded", function () {
  jam(); tandaiNav();
  setInterval(jam, 1000);
  muatFragmen();
});
