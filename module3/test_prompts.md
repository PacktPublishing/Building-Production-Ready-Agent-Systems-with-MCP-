# Module 3 Test Prompts

Pre-written prompts for each demo scenario. Copy-paste into the dev UI.

---

## Part 2: First Tests (Opus + Logical Tools)

### BR-1: Project Overview
```
What's the status of the Website Redesign project?
```

### BR-2: Task Search
```
Show me all tasks assigned to Bob that are in progress.
```

### BR-3: Task Details
```
Give me the details on task TSK-005, including any recent comments.
```

### BR-4: Status Transition
```
Move task TSK-005 to in-review.
```

### BR-5: Task Creation
```
Create a new task in the Website Redesign project: "Update footer links" assigned to Alice, high priority, due next Friday.
```

### BR-6: Comments
```
Add a comment to TSK-005 saying "Ready for QA -- all unit tests passing."
```

### Multi-Step (BR-4 + BR-6 combined)
```
Move task TSK-005 to in-review and add a comment saying "Ready for QA."
```

---

## Part 3: Model Contrast

### Scenario 1: Simple Request (both models should succeed with logical tools)
```
What's the status of the Website Redesign project?
```

### Scenario 2: Multi-Step (reveals capability gap with logical tools)
```
Move task TSK-005 to in-review and add a comment saying "Ready for QA."
```

### Scenario 3: Project Overview with Meta-Tools (reveals capability gap)
```
What's the status of the Website Redesign project?
```

Use this same prompt with:
1. Opus + meta-tools -- succeeds after multiple tool calls
2. Qwen 1.5B + meta-tools -- struggles or fails

---

## Part 4: Instruction Iteration (Qwen + Logical + Improved Instructions)

### Re-test multi-step after adding composed system instruction
```
Move task TSK-005 to in-review and add a comment saying "Ready for QA."
```

### Test name resolution guidance
```
Show me all of Bob's blocked tasks.
```

### Test formatting guidance
```
Give me an overview of the Website Redesign project, focusing on what needs attention.
```

---

## Part 5: Multi-Agent Delegation (Qwen + Expert)

### Compound request: simple + complex
```
What's the status of the Website Redesign project? And also find all blocked tasks across all projects and tell me who's responsible.
```

### Pure delegation: cross-project analysis
```
Which team members have the most overdue tasks across all projects? Summarize by person.
```

### Direct tool usage: verify simple path still works
```
Add a comment to TSK-005 saying "Discussed in standup -- unblocked now."
```
