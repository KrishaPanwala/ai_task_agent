// ✅ Add this function at the top
function formatTime(rawTime) {
    const date = new Date(rawTime + 'Z'); // treat as UTC
    return date.toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata',
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    });
}

async function addTask() {
    let message = document.getElementById("taskInput").value;
    await fetch(`/extract?message=${message}`);
    loadTasks();
}

async function loadTasks() {
    let response = await fetch("/tasks");
    let tasks = await response.json();
    let taskList = document.getElementById("taskList");
    taskList.innerHTML = "";
    tasks.forEach(task => {
        taskList.innerHTML += `
            <div class="task">
                ${task.task} - ⏰ ${formatTime(task.time)}
                <button onclick="deleteTask(${task.id})">Delete</button>
            </div>
        `;
    });
}

async function deleteTask(id) {
    await fetch(`/tasks/${id}`, { method: "DELETE" });
    loadTasks();
}

loadTasks();