// Program Oluşturucu — seçilen derslerden çakışmayan haftalık senaryolar üretir.
// "Tüm Dersler" sekmesinin kullandığı aynı data/courses.json'u okur; hiçbir
// ders verisi burada elle yazılmaz (hardcode edilmez), her şey canlı veriden
// gelir. Bir dersin gün/saat bilgisi ayrıştırılamıyorsa o ders programlayıcıya
// dahil edilmez ve bu açıkça belirtilir (ASLA tahmin edilerek doldurulmaz).

const BUILDER_DAY_CANON = [
  { key: "Pazartesi", match: ["pazartesi"] },
  { key: "Salı", match: ["sali", "salı"] }, // fold sonrası "salı" -> "sali"
  { key: "Çarşamba", match: ["carsamba"] },
  { key: "Perşembe", match: ["persembe"] },
  { key: "Cuma", match: ["cuma"] },
  { key: "Cumartesi", match: ["cumartesi"] },
  { key: "Pazar", match: ["pazar"] },
];
const BUILDER_DAY_ORDER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"];
const BUILDER_DAY_COLOR = {
  "Pazartesi": "#2F5D62", "Salı": "#8C4A34", "Çarşamba": "#5B5788",
  "Perşembe": "#9A7B2F", "Cuma": "#3E6B4F", "Cumartesi": "#7A5C99", "Pazar": "#9A3B3B",
};

const _BFOLD = str => (str || "").toString().trim().toLowerCase()
  .replace(/ı/g, "i").replace(/i̇/g, "i")
  .replace(/ş/g, "s").replace(/ğ/g, "g").replace(/ç/g, "c")
  .replace(/ö/g, "o").replace(/ü/g, "u");

function normalizeDay(raw) {
  const folded = _BFOLD(raw);
  if (!folded) return null;
  for (const d of BUILDER_DAY_CANON) {
    if (d.match.some(m => folded.includes(m))) return d.key;
  }
  return null;
}

// "12:40-16:30", "09.40-12.30", "08:40-9:30" gibi biçimleri dakikaya çevirir.
function parseTimeRange(raw) {
  if (!raw) return null;
  const m = String(raw).match(/(\d{1,2})[.:](\d{2})\s*-\s*(\d{1,2})[.:](\d{2})/);
  if (!m) return null;
  const start = Number(m[1]) * 60 + Number(m[2]);
  const end = Number(m[3]) * 60 + Number(m[4]);
  if (end <= start) return null; // mantıksız aralık, güvenmiyoruz
  return { start, end, label: `${m[1].padStart(2, "0")}:${m[2]}–${m[3].padStart(2, "0")}:${m[4]}` };
}

// Ders kodundan "şube/bölme" bilgisini atıp aile anahtarı çıkarır
// (örn. "PSL 339-02" ve "PSL339-04" -> "PSL339"). Bu sadece arayüzde
// "aynı dersin farklı şubeleri" gruplamak için kullanılan bir anahtardır,
// gösterilen veriye dokunmaz.
function familyKeyOf(code) {
  if (!code) return null;
  const m = code.match(/([A-ZÇĞİÖŞÜ]{2,5})\s*[\s-]?\s*(\d{3})/i);
  if (m) return _BFOLD(m[1] + m[2]).toUpperCase();
  return _BFOLD(code).toUpperCase();
}

let BUILDER_DEPTS = []; // status === "ok" olan bölümler
let BUILDER_FAMILIES = []; // [{key, deptId, deptName, name, sections:[{code, meetings:[...], instructor, room, raw:[...]}]}]
let BUILDER_SKIPPED = 0; // gün/saat ayrıştırılamadığı için dahil edilemeyen satır sayısı

function buildFamiliesFromDepartments(departments) {
  BUILDER_DEPTS = departments.filter(d => d.status === "ok" && d.courses && d.courses.length);
  const familyMap = new Map(); // deptId+familyKey -> family
  const sectionMap = new Map(); // deptId+code -> section (aynı kod = aynı şube, birden fazla toplantısı olabilir)
  BUILDER_SKIPPED = 0;

  for (const dept of BUILDER_DEPTS) {
    for (const course of dept.courses) {
      const day = normalizeDay(course.day);
      const time = parseTimeRange(course.time);
      if (!day || !time || !course.code) {
        BUILDER_SKIPPED++;
        continue;
      }
      const fam = familyKeyOf(course.code) || course.code;
      const famMapKey = dept.id + "::" + fam;
      const secMapKey = dept.id + "::" + course.code;

      if (!familyMap.has(famMapKey)) {
        familyMap.set(famMapKey, {
          key: famMapKey, deptId: dept.id, deptName: dept.name,
          name: course.name || course.code, sections: [],
        });
      }
      const family = familyMap.get(famMapKey);
      // aile içindeki ilk anlamlı isme sahip çıkalım (bazı satırlarda ad boş olabilir)
      if (!family.name && course.name) family.name = course.name;

      if (!sectionMap.has(secMapKey)) {
        const section = {
          code: course.code, meetings: [],
          instructor: course.instructor || null,
          room: course.room || null,
          classYear: course.class_year || null,
        };
        sectionMap.set(secMapKey, section);
        family.sections.push(section);
      }
      const section = sectionMap.get(secMapKey);
      section.meetings.push({ day, ...time, room: course.room || null });
      // aynı şubenin farklı toplantılarında derslik/hoca farklıysa ilkini koru,
      // hiçbirini uydurmuyoruz — sadece ilk görüleni gösteriyoruz.
      if (!section.instructor && course.instructor) section.instructor = course.instructor;
      if (!section.room && course.room) section.room = course.room;
    }
  }

  BUILDER_FAMILIES = [...familyMap.values()].sort((a, b) =>
    a.deptName.localeCompare(b.deptName, "tr") || a.name.localeCompare(b.name, "tr")
  );
}

function meetingsOverlap(a, b) {
  if (a.day !== b.day) return false;
  return a.start < b.end && b.start < a.end;
}
function sectionsConflict(secA, secB) {
  for (const ma of secA.meetings) for (const mb of secB.meetings) {
    if (meetingsOverlap(ma, mb)) return true;
  }
  return false;
}

// ---------------- UI state ----------------
const builderSelected = new Set(); // family.key set
const builderOffDays = new Set();
let builderActiveDepts = new Set(); // bölüm filtre chip'leri (builder sekmesine özel)
let builderQuery = "";

function initBuilder(departments) {
  buildFamiliesFromDepartments(departments);

  const deptChipsEl = document.getElementById("builderDeptChips");
  deptChipsEl.innerHTML = "";
  builderActiveDepts = new Set(BUILDER_DEPTS.map(d => d.id));
  BUILDER_DEPTS.forEach(d => {
    const chip = document.createElement("button");
    chip.className = "chip active";
    chip.textContent = d.name;
    chip.dataset.deptId = d.id;
    chip.addEventListener("click", () => {
      if (builderActiveDepts.has(d.id)) { builderActiveDepts.delete(d.id); chip.classList.remove("active"); }
      else { builderActiveDepts.add(d.id); chip.classList.add("active"); }
      renderBuilderGroups();
    });
    deptChipsEl.appendChild(chip);
  });

  const skipNote = document.getElementById("builderSkipNote");
  if (BUILDER_SKIPPED > 0) {
    skipNote.hidden = false;
    skipNote.textContent = `Not: ${BUILDER_SKIPPED} ders satırının gün/saat bilgisi eksik ya da ayrıştırılamadığı için program oluşturucuya dahil edilemedi (yine de "Tüm Dersler" listesinde görünür).`;
  } else {
    skipNote.hidden = true;
  }

  document.getElementById("builderSearch").addEventListener("input", (e) => {
    builderQuery = _BFOLD(e.target.value);
    renderBuilderGroups();
  });

  document.getElementById("offDayChips").addEventListener("click", (e) => {
    if (e.target.tagName !== "BUTTON") return;
    const day = e.target.dataset.day;
    if (builderOffDays.has(day)) { builderOffDays.delete(day); e.target.classList.remove("active"); }
    else { builderOffDays.add(day); e.target.classList.add("active"); }
  });

  document.getElementById("clearSelectionBtn").addEventListener("click", () => {
    builderSelected.clear();
    renderBuilderGroups();
    document.getElementById("builderResults").innerHTML = "";
  });

  document.getElementById("generateBtn").addEventListener("click", generateSchedules);

  renderBuilderGroups();
}

function renderBuilderGroups() {
  const container = document.getElementById("groupContainer");
  container.innerHTML = "";
  const visible = BUILDER_FAMILIES.filter(f => {
    if (!builderActiveDepts.has(f.deptId)) return false;
    if (!builderQuery) return true;
    const hay = _BFOLD(f.name + " " + f.sections.map(s => s.code + " " + (s.instructor || "")).join(" ") + " " + f.deptName);
    return hay.includes(builderQuery);
  });

  if (visible.length === 0) {
    container.innerHTML = '<div class="empty-state">Bu filtrelerle eşleşen, saat bilgisi olan ders bulunamadı.</div>';
    updateBuilderStatus();
    return;
  }

  visible.forEach(fam => {
    const card = document.createElement("div");
    card.className = "group-card" + (builderSelected.has(fam.key) ? " selected" : "");
    const sectionCount = fam.sections.length;
    card.innerHTML = `
      <div class="group-head">
        <input type="checkbox" ${builderSelected.has(fam.key) ? "checked" : ""} data-key="${fam.key}">
        <div>
          <div class="g-title">${escapeHtml(fam.name)}</div>
          <div class="g-meta">${escapeHtml(fam.deptName)} · ${sectionCount} şube</div>
        </div>
      </div>
      <div class="section-list">
        ${fam.sections.map(s => `
          <div class="section-row">
            <span class="course-code">${escapeHtml(s.code)}</span>
            ${s.meetings.map(m => `<span class="day-tag" style="background:${BUILDER_DAY_COLOR[m.day] || '#888'}">${m.day} ${m.label}${m.room ? " · " + escapeHtml(m.room) : ""}</span>`).join(" ")}
            ${s.instructor ? `<b>${escapeHtml(s.instructor)}</b>` : '<span style="opacity:.6">Öğretim üyesi belirtilmemiş</span>'}
          </div>
        `).join("")}
      </div>
    `;
    card.querySelector("input").addEventListener("change", (e) => {
      if (e.target.checked) builderSelected.add(fam.key);
      else builderSelected.delete(fam.key);
      card.classList.toggle("selected", e.target.checked);
      updateBuilderStatus();
    });
    container.appendChild(card);
  });
  updateBuilderStatus();
}

function updateBuilderStatus() {
  const el = document.getElementById("selectionStatus");
  el.textContent = builderSelected.size === 0
    ? "Henüz ders seçilmedi."
    : `${builderSelected.size} ders seçildi.`;
}

function downloadCardAsPng(cardEl, filename, triggerBtn) {
  if (typeof html2canvas === "undefined") {
    alert("Görsel oluşturma kütüphanesi yüklenemedi. İnternet bağlantını kontrol edip tekrar dene.");
    return;
  }
  const originalLabel = triggerBtn ? triggerBtn.textContent : null;
  if (triggerBtn) { triggerBtn.textContent = "Hazırlanıyor…"; triggerBtn.disabled = true; }
  html2canvas(cardEl, {
    backgroundColor: "#ffffff", scale: 2,
    ignoreElements: el => el.classList && el.classList.contains("sc-download-btn"),
  }).then(canvas => {
    const link = document.createElement("a");
    link.download = filename;
    link.href = canvas.toDataURL("image/png");
    link.click();
  }).catch(() => {
    alert("Görsel oluşturulurken bir sorun oluştu.");
  }).finally(() => {
    if (triggerBtn) { triggerBtn.textContent = originalLabel; triggerBtn.disabled = false; }
  });
}

function generateSchedules() {
  const resultsEl = document.getElementById("builderResults");
  resultsEl.innerHTML = "";

  const chosenFamilies = BUILDER_FAMILIES.filter(f => builderSelected.has(f.key));
  if (chosenFamilies.length === 0) {
    resultsEl.innerHTML = '<div class="empty-state">Önce en az bir ders seçmelisin.</div>';
    return;
  }

  // Boş bırakılacak gün kısıtı: o güne toplantısı düşen şubeler havuzdan çıkar
  // (dersin diğer şubeleri hâlâ kullanılabilir; ders tamamen atlanabilir de).
  const usableSections = chosenFamilies.map(f =>
    f.sections.filter(sec => !sec.meetings.some(m => builderOffDays.has(m.day)))
  );

  const upperBound = usableSections.reduce((acc, secs) => acc * (secs.length + 1), 1);
  if (upperBound > 2000000) {
    resultsEl.innerHTML = '<div class="conflict-note">Seçtiğin derslerin şube sayısı aramayı çok büyütüyor. Lütfen seçimi daraltarak tekrar dene.</div>';
    return;
  }

  const assignments = [];
  const LIMIT = 300000;
  let aborted = false;

  function backtrack(i, chosen) {
    if (assignments.length > LIMIT) { aborted = true; return; }
    if (i === chosenFamilies.length) {
      if (chosen.length > 0) assignments.push(chosen.slice());
      return;
    }
    backtrack(i + 1, chosen); // bu dersi atla
    if (aborted) return;
    for (const sec of usableSections[i]) {
      if (chosen.every(c => !sectionsConflict(c, sec))) {
        chosen.push(sec);
        backtrack(i + 1, chosen);
        chosen.pop();
        if (aborted) return;
      }
    }
  }
  backtrack(0, []);

  if (aborted) {
    resultsEl.innerHTML = '<div class="conflict-note">Seçtiğin derslerin kombinasyon sayısı çok fazla. Lütfen seçimi biraz daraltarak tekrar dene.</div>';
    return;
  }
  if (assignments.length === 0) {
    const dayNote = builderOffDays.size ? ` (seçtiğin ${[...builderOffDays].join(", ")} günü/günlerini boş bırakarak)` : "";
    resultsEl.innerHTML = `<div class="empty-state">Seçtiğin derslerin tüm şubeleri${dayNote} birbiriyle çakışıyor — bu havuzdan tek bir ders bile içeren çakışmasız bir program yok.</div>`;
    return;
  }

  // Sadece "maksimal" programları göster: seçilen ama kullanılmayan hiçbir
  // dersin eklenemeyeceği programlar. Daha küçük alt kümeler elenir.
  const maximal = assignments.filter(chosen => {
    for (let i = 0; i < chosenFamilies.length; i++) {
      const alreadyUsed = usableSections[i].some(sec => chosen.includes(sec));
      if (alreadyUsed) continue;
      const canAdd = usableSections[i].some(sec => chosen.every(c => !sectionsConflict(c, sec)));
      if (canAdd) return false;
    }
    return true;
  });
  maximal.sort((a, b) => b.length - a.length);

  const maxSize = maximal[0].length;
  const dayNote = builderOffDays.size ? `, ${[...builderOffDays].join(", ")} boş` : "";
  const summary = document.createElement("div");
  summary.className = "result-summary";
  summary.textContent = `${chosenFamilies.length} seçili ders arasından ${maximal.length} farklı çakışmasız program bulundu (en fazla ${maxSize} ders içeren programlar var${dayNote}).`;
  resultsEl.appendChild(summary);

  maximal.slice(0, 60).forEach((combo, idx) => {
    resultsEl.appendChild(renderScheduleCard(combo, idx + 1, chosenFamilies));
  });
  if (maximal.length > 60) {
    const note = document.createElement("div");
    note.className = "conflict-note";
    note.textContent = `${maximal.length} senaryodan ilk 60 tanesi gösteriliyor. Daha az senaryo görmek için seçimi daraltabilirsin.`;
    resultsEl.appendChild(note);
  }
}

function renderScheduleCard(combo, num, chosenFamilies) {
  const card = document.createElement("div");
  card.className = "schedule-card";

  const head = document.createElement("div");
  head.className = "sc-head";
  const headLabel = document.createElement("span");
  headLabel.textContent = `Senaryo ${num} — ${combo.length} ders`;
  const downloadBtn = document.createElement("button");
  downloadBtn.className = "sc-download-btn";
  downloadBtn.textContent = "PNG indir";
  downloadBtn.addEventListener("click", () => downloadCardAsPng(card, `senaryo-${num}.png`, downloadBtn));
  head.appendChild(headLabel);
  head.appendChild(downloadBtn);
  card.appendChild(head);

  const allMeetings = combo.flatMap(sec => sec.meetings.map(m => ({ ...m, sec })));
  const minStart = Math.min(8 * 60 + 30, ...allMeetings.map(m => m.start));
  const maxEnd = Math.max(17 * 60 + 30, ...allMeetings.map(m => m.end));
  const SLOT = 30;
  const MIN_START = Math.floor(minStart / SLOT) * SLOT;
  const MIN_END = Math.ceil(maxEnd / SLOT) * SLOT;
  const rows = Math.ceil((MIN_END - MIN_START) / SLOT);

  const grid = document.createElement("div");
  grid.className = "grid-week";
  grid.style.gridTemplateColumns = "54px repeat(" + BUILDER_DAY_ORDER.slice(0, 5).length + ", 1fr)";

  const cornerCell = document.createElement("div");
  cornerCell.className = "head-cell";
  cornerCell.style.borderLeft = "none";
  grid.appendChild(cornerCell);
  const daysToShow = BUILDER_DAY_ORDER.slice(0, 5);
  daysToShow.forEach(d => {
    const h = document.createElement("div");
    h.className = "head-cell";
    h.textContent = d;
    grid.appendChild(h);
  });

  const timeCol = document.createElement("div");
  timeCol.style.position = "relative";
  timeCol.style.height = (rows * 20) + "px";
  for (let r = 0; r < rows; r++) {
    if (r % 2 === 0) {
      const t = MIN_START + r * SLOT;
      const hh = String(Math.floor(t / 60)).padStart(2, "0");
      const mm = String(t % 60).padStart(2, "0");
      const lab = document.createElement("div");
      lab.className = "time-col";
      lab.style.position = "absolute";
      lab.style.top = (r * 20) + "px";
      lab.style.right = "4px";
      lab.style.border = "none";
      lab.textContent = `${hh}:${mm}`;
      timeCol.appendChild(lab);
    }
  }
  grid.appendChild(timeCol);

  daysToShow.forEach(day => {
    const col = document.createElement("div");
    col.style.position = "relative";
    col.style.height = (rows * 20) + "px";
    col.style.borderLeft = "1px solid var(--border)";
    for (let r = 0; r < rows; r++) {
      const line = document.createElement("div");
      line.style.position = "absolute";
      line.style.top = (r * 20) + "px";
      line.style.left = "0";
      line.style.width = "100%";
      line.style.borderBottom = "1px solid var(--border)";
      line.style.height = "20px";
      col.appendChild(line);
    }
    allMeetings.filter(m => m.day === day).forEach(m => {
      const topRow = (m.start - MIN_START) / SLOT;
      const spanRows = (m.end - m.start) / SLOT;
      const block = document.createElement("div");
      block.className = "block";
      block.style.background = BUILDER_DAY_COLOR[day] || "#888";
      block.style.top = (topRow * 20) + "px";
      block.style.height = Math.max(spanRows * 20 - 2, 16) + "px";
      block.title = `${m.sec.code} — ${m.sec.instructor || ""}`;
      block.innerHTML = `<div style="font-weight:600;">${escapeHtml(m.sec.code)}</div><div>${m.label}</div>`;
      col.appendChild(block);
    });
    grid.appendChild(col);
  });
  card.appendChild(grid);

  const list = document.createElement("div");
  list.className = "schedule-list";
  combo.slice().sort((a, b) => {
    const am = a.meetings[0], bm = b.meetings[0];
    return BUILDER_DAY_ORDER.indexOf(am.day) - BUILDER_DAY_ORDER.indexOf(bm.day) || am.start - bm.start;
  }).forEach(sec => {
    const fam = chosenFamilies.find(f => f.sections.includes(sec));
    const row = document.createElement("div");
    row.className = "row";
    const meetingsLabel = sec.meetings.map(m => `${m.day} ${m.label}${m.room ? " (" + m.room + ")" : ""}`).join(" · ");
    row.innerHTML = `
      <span class="name">${escapeHtml(fam ? fam.name : sec.code)}</span>
      <span class="meta">${escapeHtml(sec.code)}</span>
      <span class="meta">${escapeHtml(sec.instructor || "—")}</span>
      <span class="meta">${escapeHtml(meetingsLabel)}</span>
    `;
    list.appendChild(row);
  });
  card.appendChild(list);

  return card;
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
