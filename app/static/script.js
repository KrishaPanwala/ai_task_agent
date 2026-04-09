// ─── Globals ─────────────────────────────────────────────────────────────────
let allTasks = [];
let currentTab = 'all';

// ─── Utilities ───────────────────────────────────────────────────────────────
function parseTaskTime(timeStr) {
    const cleaned = timeStr.replace(" at ", " ");
    return new Date(cleaned);
}

function getCountdown(timeStr) {
    const date = parseTaskTime(timeStr);
    const now = new Date();
    const diff = date - now;
    if (isNaN(diff)) return { text: "", overdue: false };
    const abs = Math.abs(diff);
    const mins = Math.floor(abs / 60000);
    const hrs = Math.floor(mins / 60);
    const days = Math.floor(hrs / 24);
    let text = "";
    if (days > 0) text = `${days}d ${hrs % 24}h`;
    else if (hrs > 0) text = `${hrs}h ${mins % 60}m`;
    else if (mins > 0) text = `${mins}m`;
    else text = "< 1 min";
    return {
        text: diff < 0 ? `⚠️ Overdue by ${text}` : `⏳ in ${text}`,
        overdue: diff < 0
    };
}

function showToast(msg) {
    let toast = document.getElementById("toast");
    if (!toast) {
        toast = document.createElement("div");
        toast.id = "toast";
        toast.className = "toast";
        document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 3000);
}

function formatHour(h) {
    const ampm = h >= 12 ? "PM" : "AM";
    const hour = h % 12 === 0 ? 12 : h % 12;
    return `${String(hour).padStart(2, '0')}:00 ${ampm}`;
}

function isSameDay(date1, date2) {
    return date1.getFullYear() === date2.getFullYear() &&
           date1.getMonth() === date2.getMonth() &&
           date1.getDate() === date2.getDate();
}

// ─── Auth ─────────────────────────────────────────────────────────────────────
async function loadUserInfo() {
    try {
        const res = await fetch("/me");
        if (res.status === 401) { window.location.href = "/login"; return; }
        const user = await res.json();
        document.getElementById("welcomeUser").textContent = `👤 ${user.username}`;
        if (!user.chat_id) {
            document.getElementById("chatIdWarning").style.display = "flex";
        }
    } catch { window.location.href = "/login"; }
}

async function saveChatId() {
    const chatId = document.getElementById("chatIdInput").value.trim();
    if (!chatId) { showToast("⚠️ Enter your Chat ID"); return; }
    const form = new FormData();
    form.append("chat_id", chatId);
    const res = await fetch("/update-chat-id", { method: "POST", body: form });
    const data = await res.json();
    if (data.status === "updated") {
        document.getElementById("chatIdWarning").style.display = "none";
        showToast("✅ Telegram Chat ID saved!");
    }
}

async function logout() {
    try {
        await fetch("/logout", { method: "POST", credentials: "include" });
    } catch {}
    document.cookie = "access_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    window.location.href = "/login";
}

// ─── Tab Switching ────────────────────────────────────────────────────────────
function switchTab(tab) {
    currentTab = tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelector(`[onclick="switchTab('${tab}')"]`).classList.add('active');
    document.getElementById(`tab-${tab}`).classList.add('active');

    if (tab === 'today') renderToday();
    if (tab === 'weekly') renderWeekly();
}

// ─── Task API ─────────────────────────────────────────────────────────────────
async function fetchTasks() {
    const res = await fetch("/tasks");
    if (res.status === 401) { window.location.href = "/login"; return []; }
    allTasks = await res.json();
    updateStats();
    return allTasks;
}

function updateStats() {
    const now = new Date();
    let overdue = 0, upcoming = 0, recurring = 0;
    allTasks.forEach(t => {
        const d = parseTaskTime(t.time);
        if (isNaN(d)) return;
        if (d < now) overdue++;
        else upcoming++;
        if (t.is_recurring) recurring++;
    });
    document.getElementById("totalCount").textContent = allTasks.length;
    document.getElementById("upcomingCount").textContent = upcoming;
    document.getElementById("overdueCount").textContent = overdue;
    document.getElementById("recurringCount").textContent = recurring;
}

async function addTask(prefillTime = null) {
    const input = document.getElementById("taskInput");
    const btn = document.getElementById("addBtn");
    const btnText = document.getElementById("btnText");
    let message = input.value.trim();

    if (!message) { showToast("⚠️ Please enter a reminder!"); return; }

    // If adding from time slot, append time to message
    if (prefillTime) {
        message = `${message} at ${prefillTime}`;
    }

    btn.disabled = true;
    btnText.textContent = "Adding...";

    try {
        const res = await fetch(`/extract?message=${encodeURIComponent(message)}`);
        const data = await res.json();
        if (data.error) {
            showToast("❌ " + data.error);
        } else {
            input.value = "";
            showToast("✅ Reminder added!");
            await fetchTasks();
            if (currentTab === 'all') loadTasks();
            if (currentTab === 'today') renderToday();
            if (currentTab === 'weekly') renderWeekly();
        }
    } catch { showToast("❌ Something went wrong!"); }

    btn.disabled = false;
    btnText.textContent = "➕ Add Reminder";
}

async function deleteTask(id) {
    await fetch(`/tasks/${id}`, { method: "DELETE" });
    showToast("🗑️ Reminder deleted!");
    await fetchTasks();
    if (currentTab === 'all') loadTasks();
    if (currentTab === 'today') renderToday();
    if (currentTab === 'weekly') renderWeekly();
}

// ─── Tab 1: All Reminders ─────────────────────────────────────────────────────
async function loadTasks() {
    const taskList = document.getElementById("taskList");
    taskList.innerHTML = `<div class="loading">Loading reminders...</div>`;
    await fetchTasks();

    if (allTasks.length === 0) {
        taskList.innerHTML = `
            <div class="empty-state">
                <div style="font-size:3rem">📭</div>
                <p>No reminders yet! Add one above.</p>
            </div>`;
        return;
    }

    taskList.innerHTML = "";
    allTasks.forEach(task => {
        const countdown = getCountdown(task.time);
        const cardClass = countdown.overdue ? "overdue" : task.is_recurring ? "recurring" : "upcoming";
        let badges = `<span class="badge ${cardClass}">${countdown.overdue ? "⚠️ Overdue" : task.is_recurring ? "🔁 Recurring" : "✅ Upcoming"}</span>`;
        if (task.is_recurring && task.recur_type) {
            badges += `<span class="badge recurring">🔁 ${task.recur_type}</span>`;
        }
        taskList.innerHTML += `
            <div class="task-card ${cardClass}">
                <div class="task-info">
                    <div class="task-name">📌 ${task.task}</div>
                    <div class="task-time">⏰ ${task.time}</div>
                    <div class="task-countdown ${countdown.overdue ? 'overdue' : ''}">${countdown.text}</div>
                    <div class="badges">${badges}</div>
                </div>
                <button class="delete-btn" onclick="deleteTask(${task.id})">🗑️ Delete</button>
            </div>`;
    });
}

// ─── Tab 2: Today Planner ─────────────────────────────────────────────────────
async function renderToday() {
    const planner = document.getElementById("todayPlanner");
    planner.innerHTML = `<div class="loading">Loading today's plan...</div>`;
    await fetchTasks();

    const now = new Date();
    const today = now;

    // Update title
    document.getElementById("todayTitle").textContent =
        `📅 ${today.toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}`;

    // Filter today's tasks
    const todayTasks = allTasks.filter(t => {
        const d = parseTaskTime(t.time);
        return isSameDay(d, today);
    });

    planner.innerHTML = "";

    // Hours from 6 AM to 11 PM
    for (let h = 6; h <= 23; h++) {
        const slotTime = new Date(today);
        slotTime.setHours(h, 0, 0, 0);
        const isCurrentHour = now.getHours() === h;
        const isPast = now.getHours() > h;

        // Find tasks in this hour slot
        const slotTasks = todayTasks.filter(t => {
            const d = parseTaskTime(t.time);
            return d.getHours() === h;
        });

        const slotClass = isCurrentHour ? "time-slot current" : isPast ? "time-slot past" : "time-slot";

        let tasksHtml = "";
        slotTasks.forEach(task => {
            const d = parseTaskTime(task.time);
            const timeStr = d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });
            tasksHtml += `
                <div class="slot-task ${task.is_recurring ? 'recurring' : ''}">
                    <span class="slot-task-time">${timeStr}</span>
                    <span class="slot-task-name">${task.task}</span>
                    ${task.is_recurring ? '<span class="slot-badge">🔁</span>' : ''}
                    <button onclick="deleteTask(${task.id})" class="slot-delete">✕</button>
                </div>`;
        });

        // Inline add form for this slot
        const slotId = `slot-${h}`;
        const formattedHour = formatHour(h);

        planner.innerHTML += `
            <div class="${slotClass}" id="${slotId}">
                <div class="slot-header">
                    <span class="slot-time">${formattedHour}</span>
                    ${isCurrentHour ? '<span class="now-badge">NOW</span>' : ''}
                    <button class="slot-add-btn" onclick="toggleSlotInput(${h})">+</button>
                </div>
                ${tasksHtml}
                <div class="slot-input-box" id="slot-input-${h}" style="display:none">
                    <input type="text" id="slot-text-${h}" placeholder="What to remind at ${formattedHour}?"
                        onkeypress="if(event.key==='Enter') addFromSlot(${h})">
                    <button onclick="addFromSlot(${h})">Add</button>
                    <button onclick="toggleSlotInput(${h})" class="cancel-btn">Cancel</button>
                </div>
            </div>`;
    }
}

function toggleSlotInput(h) {
    const box = document.getElementById(`slot-input-${h}`);
    box.style.display = box.style.display === 'none' ? 'flex' : 'none';
    if (box.style.display === 'flex') {
        document.getElementById(`slot-text-${h}`).focus();
    }
}

async function addFromSlot(h) {
    const input = document.getElementById(`slot-text-${h}`);
    const text = input.value.trim();
    if (!text) { showToast("⚠️ Enter a reminder!"); return; }

    const now = new Date();
    const slotTime = new Date(now);
    slotTime.setHours(h, 0, 0, 0);

    const timeStr = slotTime.toLocaleTimeString('en-IN', {
        hour: '2-digit', minute: '2-digit', hour12: true
    });

    const message = `${text} at ${timeStr} today`;
    const btn = document.getElementById("addBtn");
    const btnText = document.getElementById("btnText");

    btn.disabled = true;
    btnText.textContent = "Adding...";

    try {
        const res = await fetch(`/extract?message=${encodeURIComponent(message)}`);
        const data = await res.json();
        if (data.error) {
            showToast("❌ " + data.error);
        } else {
            input.value = "";
            toggleSlotInput(h);
            showToast("✅ Reminder added!");
            await fetchTasks();
            renderToday();
        }
    } catch { showToast("❌ Something went wrong!"); }

    btn.disabled = false;
    btnText.textContent = "➕ Add Reminder";
}

// ─── Tab 3: Weekly Planner ────────────────────────────────────────────────────
async function renderWeekly() {
    const planner = document.getElementById("weeklyPlanner");
    planner.innerHTML = `<div class="loading">Loading weekly plan...</div>`;
    await fetchTasks();

    const now = new Date();
    const startOfWeek = new Date(now);
    // Start from Monday
    const day = now.getDay();
    const diff = day === 0 ? -6 : 1 - day;
    startOfWeek.setDate(now.getDate() + diff);
    startOfWeek.setHours(0, 0, 0, 0);

    const days = [];
    for (let i = 0; i < 7; i++) {
        const d = new Date(startOfWeek);
        d.setDate(startOfWeek.getDate() + i);
        days.push(d);
    }

    const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

    planner.innerHTML = `
        <div class="weekly-grid">
            ${days.map((d, i) => {
                const isToday = isSameDay(d, now);
                const dayTasks = allTasks.filter(t => isSameDay(parseTaskTime(t.time), d));
                const dateStr = d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });

                return `
                    <div class="week-day ${isToday ? 'today' : ''}">
                        <div class="week-day-header">
                            <span class="week-day-name">${dayNames[i]}</span>
                            <span class="week-day-date">${dateStr}</span>
                            ${isToday ? '<span class="today-dot"></span>' : ''}
                        </div>
                        <div class="week-day-tasks">
                            ${dayTasks.length === 0
                                ? '<div class="no-tasks">No tasks</div>'
                                : dayTasks.map(t => {
                                    const td = parseTaskTime(t.time);
                                    const timeStr = td.toLocaleTimeString('en-IN', {
                                        hour: '2-digit', minute: '2-digit', hour12: true
                                    });
                                    return `
                                        <div class="week-task ${t.is_recurring ? 'recurring' : ''}">
                                            <span class="week-task-time">${timeStr}</span>
                                            <span class="week-task-name">${t.task}</span>
                                            <button onclick="deleteTask(${t.id})" class="week-task-delete">✕</button>
                                        </div>`;
                                }).join('')
                            }
                        </div>
                        <button class="week-add-btn" onclick="addTaskForDay('${d.toISOString()}')">+ Add</button>
                    </div>`;
            }).join('')}
        </div>`;
}

async function addTaskForDay(dateIso) {
    const date = new Date(dateIso);
    const dateStr = date.toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' });
    const task = prompt(`Add reminder for ${dateStr}:\n(e.g. "drink water at 5pm")`);
    if (!task) return;

    const message = `${task} on ${dateStr}`;
    try {
        const res = await fetch(`/extract?message=${encodeURIComponent(message)}`);
        const data = await res.json();
        if (data.error) showToast("❌ " + data.error);
        else {
            showToast("✅ Reminder added!");
            await fetchTasks();
            renderWeekly();
        }
    } catch { showToast("❌ Something went wrong!"); }
}

// ─── Init ─────────────────────────────────────────────────────────────────────
loadUserInfo();
loadTasks();
setInterval(async () => {
    await fetchTasks();
    if (currentTab === 'all') loadTasks();
    if (currentTab === 'today') renderToday();
    if (currentTab === 'weekly') renderWeekly();
}, 30000);