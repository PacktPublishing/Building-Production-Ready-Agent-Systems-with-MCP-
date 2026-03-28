# Module 2 - User Stories

These are the baseline requirements (BR) that our MadeUpTasks agent must satisfy.

| ID   | User Story                                              | Priority    |
|------|---------------------------------------------------------|-------------|
| BR-1 | Quick project overview — who's on it, what's blocked    | Must have   |
| BR-2 | Find tasks matching criteria without navigating the UI  | Must have   |
| BR-3 | Full details and recent discussion on a specific task   | Must have   |
| BR-4 | Move tasks through the workflow                         | Must have   |
| BR-5 | Create tasks and assign them by name                    | Should have |
| BR-6 | Add comments through the AI                             | Nice to have|

---

## BR-1: Project Overview

**Prompt:** "Give me an overview of Project Alpha"

**Acceptance criteria:**
- Response must include project status
- Response must include team members
- Response must include current blockers

---

## BR-2: Find Tasks

**Prompt:** "Find all blocked tasks assigned to me"

**Acceptance criteria:**
- Returns a correctly filtered list of tasks
- Only includes tasks matching both criteria (blocked status + assigned to requester)

---

## BR-3: Task Details

**Prompt:** "Show me the full details on task-003"

**Acceptance criteria:**
- Returns complete task details (title, description, status, assignee, etc.)
- Includes recent discussion/comments on the task

---

## BR-4: Transition Task

**Prompt:** "Move task-004 to review"

**Acceptance criteria:**
- Validates the state transition is allowed
- Asks for confirmation before executing
- Executes the transition upon confirmation

---

## BR-5: Create + Assign

**Prompt:** "Create a bug for login, assign to Sarah"

**Acceptance criteria:**
- Resolves "Sarah" to the correct user
- Asks for confirmation before creating
- Creates the task and assigns it in one flow

---

## BR-6: Add Comment

**Prompt:** "Add a comment to task-002: 'Waiting on API key from DevOps'"

**Acceptance criteria:**
- Adds the comment to the correct task
- Confirms the comment was posted
