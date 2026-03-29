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
                ${task.task} - ${task.time}
                <button onclick="deleteTask(${task.id})">Delete</button>
            </div>
        `;

    });
}

async function deleteTask(id) {

    await fetch(`/tasks/${id}`, {
        method: "DELETE"
    });

    loadTasks();
}

loadTasks();