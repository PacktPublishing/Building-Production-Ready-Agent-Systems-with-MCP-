# Module 6: Slide Data Points and Speaker Notes

## Part 1: Where the Tokens Go

### Token Budget Breakdown (typical single interaction)

```
Component                    Tokens      Sent Every Turn?
─────────────────────────    ──────      ────────────────
System prompt                500–2,000   Yes
Tool definitions (6 tools)   680–2,840   Yes
Conversation history         Grows       Yes
Tool call request            50–150      Per call
Tool result                  200–2,000   Per call
Agent reasoning              100–500     Yes
```

### The Multiplication Problem

**Scenario:** 6 logical tools, 5-turn conversation, 3 tool calls

With verbose descriptions (~2,840 tokens for tool defs):
```
Tool defs sent 5 times:         14,200 tokens
System prompt sent 5 times:      5,000 tokens
Tool calls + results (3):        3,600 tokens
Conversation history (growing):  4,000 tokens
Agent reasoning (5 turns):       1,500 tokens
                                ──────
Total:                          ~28,300 tokens
```

With lean descriptions (~680 tokens for tool defs):
```
Tool defs sent 5 times:          3,400 tokens
System prompt sent 5 times:      5,000 tokens
Tool calls + results (3):        3,600 tokens
Conversation history (growing):  4,000 tokens
Agent reasoning (5 turns):       1,500 tokens
                                ──────
Total:                          ~17,500 tokens
```

**Savings: 10,800 tokens (38%) — just from trimming descriptions.**

### Before/After: Lean Tool Descriptions

**Before (verbose — 470 tokens):**
```
list_tasks: This tool retrieves tasks from the specified project.
The project_id parameter should be the internal project identifier
(e.g. prj_001). Tasks are returned in creation order. The response
includes full task objects with all fields including metadata, audit
trails, webhook configurations, SLA tiers, compliance tags, time
tracking data, risk scores, and other internal system fields.
Pagination is cursor-based — if has_more is true, pass the
next_cursor value to get more results. Default page size is 20.
```

**After (lean — 18 tokens):**
```
get_project_overview: Get project details, team members, and task
status summary.
```

The model doesn't need a paragraph. It needs a clear name, a one-line
description, and typed parameters. The name does most of the work.

### Actual Numbers from the 2x2 Matrix

| Config | Avg Tokens/Case | Avg Cost/Case | Pass Rate |
|--------|----------------|---------------|-----------|
| Opus + logical | 2,847 | $0.0291 | 8/9 |
| Opus + meta | 8,920 | $0.1282 | 7/9 |
| Qwen + logical | 3,640 | $0.0000 | 4/9 |
| Qwen + meta | 6,240 | $0.0000 | 1/9 |

**Key insight:** Meta-tools cost 3–4x more tokens than logical tools for the
same task — the model needs multiple discovery round trips. But Qwen is free
locally, so the cost story is really about Opus vs. not-Opus.

---

## Part 2: Optimization Strategies

### Tier 1 — Low effort, high impact

1. **Lean tool descriptions**
   - Strip examples, verbose explanations, redundant parameter docs
   - The model infers from the function name + parameter names + types
   - Savings: 60–75% of tool definition tokens

2. **Response filtering** (already done in Module 2)
   - Raw task: ~2,000 tokens (40+ fields)
   - Shaped task: ~120 tokens (7 fields)
   - Savings: 94% per tool result
   - Over a search returning 10 tasks: 18,800 tokens saved

3. **Result summarization for history**
   - After processing, replace full tool results in history with summaries
   - "Retrieved 12 tasks: 4 open, 3 in progress, 2 blocked, 2 done, 1 in review"
   - Prevents context window bloat in multi-turn conversations

### Tier 2 — Medium effort, significant impact

4. **Dynamic tool sets**
   - Don't register all tools for every conversation
   - Use initial intent to select a subset: "status report" → overview + search only
   - 10 tools → 3 tools = 70% reduction in per-message overhead
   - Over 5 turns: 14,000 tokens saved

5. **Prompt caching**
   - Anthropic: automatic cache on static prefixes (system + tools)
   - OpenAI: similar support for structured prompts
   - If tool set is stable within a session, definitions are processed once
   - Effective 90% discount on repeated tool definition tokens

6. **Batching and prefetching**
   - `get_project_overview` = 1 tool call that fetches 3 API resources
   - Without it: agent calls 3 separate tools = 3 round trips = 3x context growth
   - Design tools for the workflow, not the API

### Tier 3 — Architectural decisions

7. **Model tiering**
   - Planning and complex reasoning: Opus/GPT-4.1
   - Simple lookups and extraction: Haiku/GPT-4.1-mini
   - Same task, 10–20x cost difference
   - The Module 3 multi-agent pattern does exactly this

8. **MCP server-side caching**
   - User list, project metadata, enum values — cache for minutes, not milliseconds
   - The helpers.py `resolve_user_name` already caches the user list

9. **Know when MCP is wrong** (see decision checklist below)

---

## Part 3: Cost in Practice

### Dollar Cost of a Single "Project Status Report"

Using BR-1 (get project overview) as the example:

| Config | Tokens | Cost | Latency |
|--------|--------|------|---------|
| Opus + logical | 3,842 | $0.0487 | 4.2s |
| Opus + meta | 14,680 | $0.2094 | 16.2s |

**The meta-tools version costs 4.3x more and takes 3.9x longer** for the
same correct answer. The model had to discover endpoints, describe them,
then execute three separate API calls. The logical tool did it in one round trip.

### Scaling: What Does a Team of 20 Cost?

Assume 20 users, 10 queries/day each, average 3,000 tokens/query (logical tools):

```
Daily tokens:  20 × 10 × 3,000 = 600,000 tokens
Monthly tokens: 600,000 × 22 workdays = 13.2M tokens

With Opus:    ~$200/month  (input) + ~$300/month (output) = ~$500/month
With Sonnet:  ~$40/month   (input) + ~$60/month  (output) = ~$100/month
With Haiku:   ~$10/month   (input) + ~$16/month  (output) = ~$26/month
```

**The model choice matters more than any optimization.** Switching from Opus
to Sonnet saves 5x. Switching from Sonnet to Haiku saves another 4x.
Lean descriptions save 38%. Both matter, but model selection dominates.

---

## "When MCP Is Wrong" Decision Checklist

Use MCP + agent when:
- [ ] The task requires **reasoning about context** (ambiguous queries, multi-step)
- [ ] The user's intent varies and can't be predicted at compile time
- [ ] The task benefits from **natural language interaction** (clarification, confirmation)
- [ ] Multiple data sources need to be **composed dynamically**

Use a direct API call / batch job / simple UI instead when:
- [ ] The workflow is **deterministic** (same steps every time)
- [ ] Processing **bulk data** (1,000 records → just write a script)
- [ ] The task is a **simple CRUD form** (create ticket with 5 fields)
- [ ] **Latency matters** more than flexibility (real-time dashboards)
- [ ] The task is a **scheduled report** (cron job, not a conversation)

**The test:** If you can write an `if/else` tree that handles all cases,
you don't need an agent. Agents earn their cost when the decision space
is too large or too ambiguous for static logic.

---

## Production Cost Anecdotes

### 1. The Token Explosion
A financial services team connected an agent to their internal API with
30 passthrough tools (one per endpoint). Tool definitions alone consumed
12,000 tokens per message. A 5-turn conversation cost $0.90 on Opus —
mostly paying for the model to re-read tool descriptions it had already seen.
After consolidating to 8 logical tools with lean descriptions: $0.12 per
conversation. 87% reduction.

### 2. The Retry Loop
A customer support agent used meta-tools to navigate a CRM API. For
complex queries, the model would call `list_endpoints` → `describe_endpoint`
→ `execute_endpoint` → get wrong results → start over. Average 8 turns per
resolution. After switching core workflows to logical tools and keeping
meta-tools for edge cases: average 2.5 turns. Cost dropped 70%, customer
satisfaction went up because responses were faster.

### 3. The Cache Win
A code review agent processed PRs with access to 6 MCP tools. System prompt
and tool definitions were identical across all PRs. Enabling Anthropic's
prompt caching made those ~3,000 tokens effectively free after the first
message in each session. Monthly costs dropped 40% with zero code changes.
