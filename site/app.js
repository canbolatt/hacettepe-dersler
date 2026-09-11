// Basit, framework'süz statik site mantığı.
// data/courses.json'u okuyup filtrelenebilir bir tablo olarak gösterir.

const STATUS_LABELS = {
  ok: null, // sorun yok, banner göstermeye gerek yok
  not_published: { cls: "warn", text: "Bu dönemin programı henüz yayınlanmamış." },
  pending_first_run: { cls: "warn", text: "Kaynak link doğrulandı, veri ilk otomatik güncellemede çekilecek." },
  fetch_error: { cls: "error", text: "PDF indirilemedi — kaynağa aşağıdaki linkten bakabilirsin." },
  parse_error: { cls: "error", text: "PDF indirildi ama otomatik ayrıştırılamadı — kaynağa aşağıdaki linkten bakabilirsin." },
  not_found: { cls: "error", text: "Ders programı PDF'i otomatik olarak bulunamadı." },
};

let ALL_DEPARTMENTS = [];
let ACTIVE_DEPT_IDS = new Set();

async function loadData() {
  const res = await fetch("data/courses.json", { cache: "no-store" });
  if (!res.ok) throw new Error("courses.json yüklenemedi: " + res.status);
  return res.json();
}

function fmtDate(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString("tr-TR", { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return iso;
  }
}

function renderDeptFilters(departments) {
  const container = document.getElementById("deptFilters");
  container.innerHTML = "";
  departments.forEach((d) => {
    const chip = document.createElement("button");
    chip.className = "dept-chip active";
    chip.textContent = `${d.name} (${d.courses.length})`;
    chip.dataset.deptId = d.id;
    chip.addEventListener("click", () => {
      if (ACTIVE_DEPT_IDS.has(d.id)) {
        ACTIVE_DEPT_IDS.delete(d.id);
        chip.classList.remove("active");
      } else {
        ACTIVE_DEPT_IDS.add(d.id);
        chip.classList.add("active");
      }
      renderTable();
    });
    container.appendChild(chip);
    ACTIVE_DEPT_IDS.add(d.id);
  });
}

function renderBanners(departments) {
  const container = document.getElementById("statusBanners");
  container.innerHTML = "";
  departments.forEach((d) => {
    const info = STATUS_LABELS[d.status];
    if (!info) return;
    const div = document.createElement("div");
    div.className = `banner ${info.cls}`;
    let html = `<strong>${escapeHtml(d.name)}:</strong> ${info.text}`;
    const link = d.source_pdf_url || d.last_known_stale_pdf?.url;
    if (link) {
      html += ` <a href="${escapeAttr(link)}" target="_blank" rel="noopener">Kaynağı gör →</a>`;
    }
    if (d.note) {
      html += `<br><span style="opacity:.8">${escapeHtml(d.note)}</span>`;
    }
    div.innerHTML = html;
    container.appendChild(div);
  });
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
function escapeAttr(s) { return escapeHtml(s); }

function renderTable() {
  const q = document.getElementById("searchBox").value.trim().toLowerCase();
  const tbody = document.getElementById("coursesBody");
  tbody.innerHTML = "";
  let count = 0;

  for (const dept of ALL_DEPARTMENTS) {
    if (!ACTIVE_DEPT_IDS.has(dept.id)) continue;
    for (const course of dept.courses) {
      const haystack = [
        course.code, course.name, course.instructor, dept.name,
      ].filter(Boolean).join(" ").toLowerCase();
      if (q && !haystack.includes(q)) continue;

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(dept.name)}</td>
        <td>${escapeHtml(course.code)}</td>
        <td>${escapeHtml(course.name)}</td>
        <td>${escapeHtml(course.class_year)}</td>
        <td>${escapeHtml(course.day)}</td>
        <td>${escapeHtml(course.time)}</td>
        <td>${escapeHtml(course.room)}</td>
        <td>${escapeHtml(course.instructor)}</td>
        <td>${escapeHtml(course.capacity)}</td>
        <td>${dept.source_pdf_url
          ? `<a class="src-link" href="${escapeAttr(dept.source_pdf_url)}" target="_blank" rel="noopener">PDF</a>`
          : ""}</td>
      `;
      tbody.appendChild(tr);
      count++;
    }
  }

  document.getElementById("emptyState").hidden = count > 0;
}

async function init() {
  try {
    const data = await loadData();
    ALL_DEPARTMENTS = data.departments;
    document.getElementById("generatedAt").textContent =
      `Son güncelleme kontrolü: ${fmtDate(data.generated_at)}`;
    renderDeptFilters(ALL_DEPARTMENTS);
    renderBanners(ALL_DEPARTMENTS);
    renderTable();
    document.getElementById("searchBox").addEventListener("input", renderTable);
  } catch (e) {
    document.getElementById("generatedAt").textContent =
      "Veri yüklenemedi: " + e.message;
  }
}

init();
