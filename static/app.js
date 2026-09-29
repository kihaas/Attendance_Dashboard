const STATUS_TEXT = {
  critical: "Критический риск",
  below: "Ниже порога",
  reached: "Допуск достигнут",
  good: "Хороший запас",
  no_data: "Нет данных",
};

const $ = (selector) => document.querySelector(selector);
const grid = $("#grid");
const syncBtn = $("#sync-btn");
let view = "active";

const esc = (text) =>
  String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const formatDate = (iso) =>
  new Date(iso).toLocaleString("ru-RU", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });

async function api(url, method = "GET") {
  const response = await fetch(url, { method });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Что-то пошло не так.");
  return data;
}

let toastTimer;
function toast(message, isError = false) {
  const el = $("#toast");
  el.textContent = message;
  el.className = "toast" + (isError ? " error" : "");
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), 5000);
}

function cardHtml(s) {
  const archived = view === "archive";
  const percent = s.attendance_percent;
  return `
    <article class="card ${s.status}">
      <div class="card-head">
        <h2>${esc(s.name)}</h2>
        ${archived ? "" : `<button class="menu-btn" data-menu aria-label="Действия">⋮</button>`}
      </div>
      <p class="muted">${esc(s.teacher) || "Преподаватель не указан"}</p>
      <div>
        <span class="percent">${percent.toFixed(1)}<small>%</small></span>
        <span class="status">${STATUS_TEXT[s.status]}</span>
      </div>
      <div class="bar" title="Порог 60%">
        <div class="bar-fill" style="width:${Math.min(percent, 100)}%"></div>
        <div class="bar-mark" style="left:60%"></div>
      </div>
      <div class="stats">
        <span><b>${s.present_count}</b>Посещено</span>
        <span><b>${s.absent_count}</b>Пропущено</span>
        <span><b>${s.total_count}</b>Учтено</span>
      </div>
      <p class="hint">${archived ? `Завершено ${formatDate(s.completed_at)}` : esc(s.recommendation)}</p>
      ${archived ? "" : `<div class="menu" hidden><button data-complete="${s.id}">Завершить дисциплину</button></div>`}
    </article>`;
}

async function load() {
  const empty = $("#empty");
  if (view === "active") {
    const data = await api("/api/dashboard");
    $("#last-updated").textContent = data.last_updated
      ? `Обновлено: ${formatDate(data.last_updated)}`
      : "Данные ещё не загружались";
    render(data.subjects, "Пока пусто. Нажмите «Обновить данные», чтобы загрузить дисциплины из журнала.");
  } else {
    render(await api("/api/archive"), "В архиве пока нет завершённых дисциплин.");
  }
  function render(items, emptyText) {
    grid.innerHTML = items.map(cardHtml).join("");
    empty.textContent = emptyText;
    empty.hidden = items.length > 0;
  }
}

async function safeLoad() {
  try {
    await load();
  } catch (e) {
    toast(e.message, true);
  }
}

syncBtn.addEventListener("click", async () => {
  syncBtn.disabled = true;
  syncBtn.textContent = "Обновление...";
  try {
    const r = await api("/api/sync", "POST");
    toast(`Готово: новых занятий — ${r.new_lessons}, новых дисциплин — ${r.new_subjects}.`);
  } catch (e) {
    toast(e.message, true);
  } finally {
    syncBtn.disabled = false;
    syncBtn.textContent = "Обновить данные";
    safeLoad();
  }
});

document.querySelectorAll(".tab").forEach((tab) =>
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t === tab));
    view = tab.dataset.view;
    safeLoad();
  })
);

// Делегирование кликов: меню карточки и завершение дисциплины
document.addEventListener("click", async (event) => {
  const menuBtn = event.target.closest("[data-menu]");
  document.querySelectorAll(".menu").forEach((m) => {
    m.hidden = !(menuBtn && m === menuBtn.closest(".card").querySelector(".menu") && m.hidden);
  });

  const completeBtn = event.target.closest("[data-complete]");
  if (completeBtn && confirm("Завершить дисциплину? Она переместится в архив.")) {
    try {
      await api(`/api/subjects/${completeBtn.dataset.complete}/complete`, "POST");
      toast("Дисциплина перенесена в архив.");
    } catch (e) {
      toast(e.message, true);
    }
    safeLoad();
  }
});

safeLoad();