// static/script.js
let refreshInterval = null;

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

function parseTaskTime(timeStr) {
    // Convert "07 Apr 2026 at 12:30 PM" → "07 Apr 2026 12:30 PM"
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


async function addTask() {
    const input = document.getElementById("taskInput");
    const btn = document.getElementById("addBtn");
    const btnText = document.getElementById("btnText");
    const message = input.value.trim();

    if (!message) { showToast("⚠️ Please enter a reminder!"); return; }

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
            loadTasks();
        }
    } catch {
        showToast("❌ Something went wrong!");
    }

    btn.disabled = false;
    btnText.textContent = "Add Reminder";
}

async function loadTasks() {
    const taskList = document.getElementById("taskList");
    taskList.innerHTML = `<div class="loading">Loading reminders...</div>`;

    try {
        const res = await fetch("/tasks");
        const tasks = await res.json();

        // Update stats
        const now = new Date();
        let overdue = 0, upcoming = 0, recurring = 0;

        tasks.forEach(t => {
            const d = parseTaskTime(t.time);  // ✅ use parseTaskTime instead of new Date()
            if (isNaN(d)) return;
            if (d < now) overdue++;
            else upcoming++;
            if (t.is_recurring) recurring++;
        });

        document.getElementById("totalCount").textContent = tasks.length;
        document.getElementById("upcomingCount").textContent = upcoming;
        document.getElementById("overdueCount").textContent = overdue;
        document.getElementById("recurringCount").textContent = recurring;

        if (tasks.length === 0) {
            taskList.innerHTML = `
                <div class="empty-state">
                    <div style="font-size:3rem">📭</div>
                    <p>No reminders yet! Add one above.</p>
                </div>`;
            return;
        }

        taskList.innerHTML = "";
        tasks.forEach(task => {
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

    } catch {
        taskList.innerHTML = `<div class="empty-state"><p>❌ Failed to load reminders</p></div>`;
    }
}

async function deleteTask(id) {
    await fetch(`/tasks/${id}`, { method: "DELETE" });
    showToast("🗑️ Reminder deleted!");
    loadTasks();
}

// Auto refresh every 30 seconds
loadTasks();
setInterval(loadTasks, 30000);