# Middleman Issue Assignees Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add assignee tracking to middleman issues so nd-triage can query issues by assignee.

**Architecture:** Add `assignees_json` column to issues table, extract assignees during GitHub/GitLab sync, expose `?assignee=` filter on `/api/v1/issues` endpoint, display assignees in frontend issue detail view.

**Tech Stack:** Go, SQLite, Svelte, TypeScript

**Working Directory:** `/Users/andy/code/middleman`

---

### Task 1: Database Migration

**Files:**
- Create: `internal/db/migrations/000028_add_issue_assignees.up.sql`
- Create: `internal/db/migrations/000028_add_issue_assignees.down.sql`

- [ ] **Step 1: Create up migration**

```sql
-- internal/db/migrations/000028_add_issue_assignees.up.sql
ALTER TABLE middleman_issues ADD COLUMN assignees_json TEXT NOT NULL DEFAULT '[]';
```

- [ ] **Step 2: Create down migration**

```sql
-- internal/db/migrations/000028_add_issue_assignees.down.sql
ALTER TABLE middleman_issues DROP COLUMN assignees_json;
```

- [ ] **Step 3: Run migration to verify**

Run: `go run ./cmd/middleman migrate`
Expected: Migration 28 applied successfully

- [ ] **Step 4: Commit**

```bash
git add internal/db/migrations/000028_add_issue_assignees.up.sql internal/db/migrations/000028_add_issue_assignees.down.sql
git commit -m "feat(db): add assignees_json column to issues table"
```

---

### Task 2: Update db.Issue struct

**Files:**
- Modify: `internal/db/types.go:363-383`

- [ ] **Step 1: Add AssigneesJSON field to Issue struct**

In `internal/db/types.go`, update the `Issue` struct (around line 363):

```go
type Issue struct {
	ID                 int64
	RepoID             int64
	PlatformID         int64
	PlatformExternalID string
	Number             int
	URL                string
	Title              string
	Author             string
	State              string
	Body               string
	CommentCount       int
	LabelsJSON         string    `json:"-"`
	AssigneesJSON      string    `json:"-"`  // NEW: JSON array of assignee usernames
	CreatedAt          time.Time
	UpdatedAt          time.Time
	LastActivityAt     time.Time
	ClosedAt           *time.Time
	DetailFetchedAt    *time.Time
	Starred            bool
	Labels             []Label  `json:"labels,omitempty"`
	Assignees          []string `json:"assignees,omitempty"`  // NEW: Parsed assignees
}
```

- [ ] **Step 2: Commit**

```bash
git add internal/db/types.go
git commit -m "feat(db): add AssigneesJSON and Assignees fields to Issue struct"
```

---

### Task 3: Update platform.Issue struct

**Files:**
- Modify: `internal/platform/types.go:101-117`

- [ ] **Step 1: Add Assignees field to platform.Issue**

In `internal/platform/types.go`, update the `Issue` struct (around line 101):

```go
type Issue struct {
	Repo               RepoRef
	PlatformID         int64
	PlatformExternalID string
	Number             int
	URL                string
	Title              string
	Author             string
	State              string
	Body               string
	CommentCount       int
	CreatedAt          time.Time
	UpdatedAt          time.Time
	LastActivityAt     time.Time
	ClosedAt           *time.Time
	Labels             []Label
	Assignees          []string  // NEW: Assignee usernames
}
```

- [ ] **Step 2: Commit**

```bash
git add internal/platform/types.go
git commit -m "feat(platform): add Assignees field to Issue struct"
```

---

### Task 4: Extract assignees in GitHub normalize

**Files:**
- Modify: `internal/platform/github/normalize.go`
- Test: `internal/platform/github/normalize_test.go`

- [ ] **Step 1: Write failing test for NormalizeIssue with assignees**

Add to `internal/platform/github/normalize_test.go`:

```go
func TestNormalizeIssue_ExtractsAssignees(t *testing.T) {
	require := require.New(t)

	assignee1Login := "alice"
	assignee2Login := "bob"
	ghIssue := &gh.Issue{
		ID:     gh.Ptr(int64(123)),
		Number: gh.Ptr(42),
		Title:  gh.Ptr("Test issue"),
		State:  gh.Ptr("open"),
		HTMLURL: gh.Ptr("https://github.com/owner/repo/issues/42"),
		Body:   gh.Ptr("Issue body"),
		User:   &gh.User{Login: gh.Ptr("author")},
		Assignees: []*gh.User{
			{Login: &assignee1Login},
			{Login: &assignee2Login},
		},
		CreatedAt: &gh.Timestamp{Time: time.Now()},
		UpdatedAt: &gh.Timestamp{Time: time.Now()},
	}

	issue, err := NormalizeIssue(platform.RepoRef{}, ghIssue)
	require.NoError(err)
	require.Equal([]string{"alice", "bob"}, issue.Assignees)
}

func TestNormalizeIssue_EmptyAssignees(t *testing.T) {
	require := require.New(t)

	ghIssue := &gh.Issue{
		ID:      gh.Ptr(int64(123)),
		Number:  gh.Ptr(42),
		Title:   gh.Ptr("Test issue"),
		State:   gh.Ptr("open"),
		HTMLURL: gh.Ptr("https://github.com/owner/repo/issues/42"),
		Body:    gh.Ptr("Issue body"),
		User:    &gh.User{Login: gh.Ptr("author")},
		CreatedAt: &gh.Timestamp{Time: time.Now()},
		UpdatedAt: &gh.Timestamp{Time: time.Now()},
	}

	issue, err := NormalizeIssue(platform.RepoRef{}, ghIssue)
	require.NoError(err)
	require.Empty(issue.Assignees)
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./internal/platform/github/... -run TestNormalizeIssue_ExtractsAssignees -v`
Expected: FAIL (Assignees field not populated)

- [ ] **Step 3: Update NormalizeIssue to extract assignees**

In `internal/platform/github/normalize.go`, find the `NormalizeIssue` function and add assignee extraction:

```go
func NormalizeIssue(repo RepoRef, ghIssue *gh.Issue) (*platform.Issue, error) {
	if ghIssue == nil {
		return nil, errors.New("issue is nil")
	}

	var assignees []string
	for _, a := range ghIssue.Assignees {
		if a != nil && a.Login != nil {
			assignees = append(assignees, *a.Login)
		}
	}

	issue := &platform.Issue{
		Repo:               repo,
		PlatformID:         ghIssue.GetID(),
		PlatformExternalID: ghIssue.GetNodeID(),
		Number:             ghIssue.GetNumber(),
		URL:                ghIssue.GetHTMLURL(),
		Title:              ghIssue.GetTitle(),
		Author:             loginOrEmpty(ghIssue.User),
		State:              ghIssue.GetState(),
		Body:               ghIssue.GetBody(),
		CommentCount:       ghIssue.GetComments(),
		CreatedAt:          ghIssue.GetCreatedAt().Time,
		UpdatedAt:          ghIssue.GetUpdatedAt().Time,
		LastActivityAt:     ghIssue.GetUpdatedAt().Time,
		Assignees:          assignees,
	}
	// ... rest of function
```

- [ ] **Step 4: Run test to verify it passes**

Run: `go test ./internal/platform/github/... -run TestNormalizeIssue -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add internal/platform/github/normalize.go internal/platform/github/normalize_test.go
git commit -m "feat(github): extract assignees when normalizing issues"
```

---

### Task 5: Extract assignees in GitLab/Gitea normalize

**Files:**
- Modify: `internal/platform/gitealike/normalize.go`
- Test: `internal/platform/gitealike/normalize_test.go`

- [ ] **Step 1: Write failing test for gitealike NormalizeIssue with assignees**

Add to `internal/platform/gitealike/normalize_test.go`:

```go
func TestNormalizeIssue_ExtractsAssignees(t *testing.T) {
	require := require.New(t)

	issue := &gitea.Issue{
		ID:       123,
		Index:    42,
		Title:    "Test issue",
		State:    gitea.StateOpen,
		HTMLURL:  "https://gitea.example.com/owner/repo/issues/42",
		Body:     "Issue body",
		Poster:   &gitea.User{UserName: "author"},
		Assignees: []*gitea.User{
			{UserName: "alice"},
			{UserName: "bob"},
		},
		Created: time.Now(),
		Updated: time.Now(),
	}

	normalized := NormalizeIssue(platform.RepoRef{}, issue)
	require.Equal([]string{"alice", "bob"}, normalized.Assignees)
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./internal/platform/gitealike/... -run TestNormalizeIssue_ExtractsAssignees -v`
Expected: FAIL

- [ ] **Step 3: Update NormalizeIssue to extract assignees**

In `internal/platform/gitealike/normalize.go`, update `NormalizeIssue`:

```go
func NormalizeIssue(repo platform.RepoRef, issue *gitea.Issue) *platform.Issue {
	if issue == nil {
		return nil
	}

	var assignees []string
	for _, a := range issue.Assignees {
		if a != nil {
			assignees = append(assignees, a.UserName)
		}
	}

	return &platform.Issue{
		Repo:               repo,
		PlatformID:         issue.ID,
		PlatformExternalID: strconv.FormatInt(issue.ID, 10),
		Number:             int(issue.Index),
		URL:                issue.HTMLURL,
		Title:              issue.Title,
		Author:             userNameOrEmpty(issue.Poster),
		State:              normalizeIssueState(issue.State),
		Body:               issue.Body,
		CommentCount:       int(issue.Comments),
		CreatedAt:          issue.Created,
		UpdatedAt:          issue.Updated,
		LastActivityAt:     issue.Updated,
		Assignees:          assignees,
	}
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `go test ./internal/platform/gitealike/... -run TestNormalizeIssue -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add internal/platform/gitealike/normalize.go internal/platform/gitealike/normalize_test.go
git commit -m "feat(gitealike): extract assignees when normalizing issues"
```

---

### Task 6: Update internal/github normalize to pass assignees through

**Files:**
- Modify: `internal/github/normalize.go`

- [ ] **Step 1: Update NormalizeIssue in internal/github to include assignees**

In `internal/github/normalize.go`, find `NormalizeIssue` (around line 291) and add:

```go
func NormalizeIssue(repoID int64, ghIssue *gh.Issue) (*db.Issue, error) {
	platformIssue, err := platformgithub.NormalizeIssue(platform.RepoRef{}, ghIssue)
	if err != nil {
		return nil, err
	}

	assigneesJSON := "[]"
	if len(platformIssue.Assignees) > 0 {
		b, _ := json.Marshal(platformIssue.Assignees)
		assigneesJSON = string(b)
	}

	issue := &db.Issue{
		RepoID:             repoID,
		PlatformID:         platformIssue.PlatformID,
		PlatformExternalID: platformIssue.PlatformExternalID,
		Number:             platformIssue.Number,
		URL:                platformIssue.URL,
		Title:              platformIssue.Title,
		Author:             platformIssue.Author,
		State:              platformIssue.State,
		Body:               platformIssue.Body,
		CommentCount:       platformIssue.CommentCount,
		CreatedAt:          platformIssue.CreatedAt,
		UpdatedAt:          platformIssue.UpdatedAt,
		LastActivityAt:     platformIssue.LastActivityAt,
		ClosedAt:           platformIssue.ClosedAt,
		AssigneesJSON:      assigneesJSON,
		Assignees:          platformIssue.Assignees,
	}
	// ... rest of labels handling
```

- [ ] **Step 2: Run existing tests**

Run: `go test ./internal/github/... -run NormalizeIssue -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add internal/github/normalize.go
git commit -m "feat(github): pass assignees through to db.Issue"
```

---

### Task 7: Update UpsertIssue to store assignees_json

**Files:**
- Modify: `internal/db/queries.go`
- Test: `internal/db/queries_test.go`

- [ ] **Step 1: Write failing test**

Add to `internal/db/queries_test.go`:

```go
func TestUpsertIssue_StoresAssignees(t *testing.T) {
	require := require.New(t)
	assert := Assert.New(t)
	d := openTestDB(t)
	ctx := t.Context()
	now := baseTime()
	repoID := insertTestRepo(t, d, "owner", "repo")

	issue := &db.Issue{
		RepoID:         repoID,
		PlatformID:     123,
		Number:         42,
		URL:            "https://github.com/owner/repo/issues/42",
		Title:          "Test issue",
		Author:         "author",
		State:          "open",
		AssigneesJSON:  `["alice","bob"]`,
		CreatedAt:      now,
		UpdatedAt:      now,
		LastActivityAt: now,
	}

	_, err := d.UpsertIssue(ctx, issue)
	require.NoError(err)

	// Verify stored value
	var stored string
	err = d.ReadDB().QueryRowContext(ctx,
		`SELECT assignees_json FROM middleman_issues WHERE repo_id = ? AND number = ?`,
		repoID, 42,
	).Scan(&stored)
	require.NoError(err)
	assert.JSONEq(`["alice","bob"]`, stored)
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./internal/db/... -run TestUpsertIssue_StoresAssignees -v`
Expected: FAIL (assignees_json not in INSERT)

- [ ] **Step 3: Update UpsertIssue to include assignees_json**

In `internal/db/queries.go`, find `UpsertIssue` (around line 3028) and add `assignees_json` to the INSERT:

```go
func (d *DB) UpsertIssue(ctx context.Context, issue *Issue) (int64, error) {
	canonicalizeIssueTimestamps(issue)
	_, err := d.rw.ExecContext(ctx, `
		INSERT INTO middleman_issues
		    (repo_id, platform_id, platform_external_id, number, url, title, author, state,
		     body, comment_count, labels_json, assignees_json, detail_fetched_at,
		     created_at, updated_at, last_activity_at, closed_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT (repo_id, number) DO UPDATE SET
		    platform_id = excluded.platform_id,
		    platform_external_id = excluded.platform_external_id,
		    url = excluded.url,
		    title = excluded.title,
		    author = excluded.author,
		    state = excluded.state,
		    body = excluded.body,
		    comment_count = excluded.comment_count,
		    labels_json = excluded.labels_json,
		    assignees_json = excluded.assignees_json,
		    detail_fetched_at = excluded.detail_fetched_at,
		    updated_at = excluded.updated_at,
		    last_activity_at = excluded.last_activity_at,
		    closed_at = excluded.closed_at
		WHERE excluded.updated_at >= middleman_issues.updated_at`,
		issue.RepoID,
		issue.PlatformID,
		issue.PlatformExternalID,
		issue.Number,
		issue.URL,
		issue.Title,
		issue.Author,
		issue.State,
		issue.Body,
		issue.CommentCount,
		issue.LabelsJSON,
		issue.AssigneesJSON,
		issue.DetailFetchedAt,
		issue.CreatedAt,
		issue.UpdatedAt,
		issue.LastActivityAt,
		issue.ClosedAt,
	)
	// ... rest of function
```

- [ ] **Step 4: Run test to verify it passes**

Run: `go test ./internal/db/... -run TestUpsertIssue_StoresAssignees -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add internal/db/queries.go internal/db/queries_test.go
git commit -m "feat(db): store assignees_json in UpsertIssue"
```

---

### Task 8: Update ListIssues to filter by assignee

**Files:**
- Modify: `internal/db/types.go` (ListIssuesOpts)
- Modify: `internal/db/queries.go` (ListIssues)
- Test: `internal/db/queries_test.go`

- [ ] **Step 1: Add Assignee field to ListIssuesOpts**

In `internal/db/types.go`, find `ListIssuesOpts` (around line 340) and add:

```go
type ListIssuesOpts struct {
	RepoFilters  []RepoFilter
	PlatformHost string
	RepoOwner    string
	RepoName     string
	RepoPath     string
	State        string
	KanbanState  string
	Starred      bool
	Search       string
	Assignee     string  // NEW: Filter by assignee username
	Limit        int
	Offset       int
}
```

- [ ] **Step 2: Write failing test for assignee filter**

Add to `internal/db/queries_test.go`:

```go
func TestListIssues_FilterByAssignee(t *testing.T) {
	require := require.New(t)
	assert := Assert.New(t)
	d := openTestDB(t)
	ctx := t.Context()
	now := baseTime()
	repoID := insertTestRepo(t, d, "owner", "repo")

	// Issue assigned to alice
	issue1 := &db.Issue{
		RepoID:         repoID,
		PlatformID:     1,
		Number:         1,
		URL:            "https://github.com/owner/repo/issues/1",
		Title:          "Issue 1",
		Author:         "author",
		State:          "open",
		AssigneesJSON:  `["alice"]`,
		CreatedAt:      now,
		UpdatedAt:      now,
		LastActivityAt: now,
	}
	_, err := d.UpsertIssue(ctx, issue1)
	require.NoError(err)

	// Issue assigned to bob
	issue2 := &db.Issue{
		RepoID:         repoID,
		PlatformID:     2,
		Number:         2,
		URL:            "https://github.com/owner/repo/issues/2",
		Title:          "Issue 2",
		Author:         "author",
		State:          "open",
		AssigneesJSON:  `["bob"]`,
		CreatedAt:      now,
		UpdatedAt:      now,
		LastActivityAt: now,
	}
	_, err = d.UpsertIssue(ctx, issue2)
	require.NoError(err)

	// Issue assigned to both
	issue3 := &db.Issue{
		RepoID:         repoID,
		PlatformID:     3,
		Number:         3,
		URL:            "https://github.com/owner/repo/issues/3",
		Title:          "Issue 3",
		Author:         "author",
		State:          "open",
		AssigneesJSON:  `["alice","bob"]`,
		CreatedAt:      now,
		UpdatedAt:      now,
		LastActivityAt: now,
	}
	_, err = d.UpsertIssue(ctx, issue3)
	require.NoError(err)

	// Filter by alice
	issues, err := d.ListIssues(ctx, db.ListIssuesOpts{Assignee: "alice", State: "all"})
	require.NoError(err)
	assert.Len(issues, 2)
	numbers := []int{issues[0].Number, issues[1].Number}
	assert.ElementsMatch([]int{1, 3}, numbers)

	// Filter by bob
	issues, err = d.ListIssues(ctx, db.ListIssuesOpts{Assignee: "bob", State: "all"})
	require.NoError(err)
	assert.Len(issues, 2)
	numbers = []int{issues[0].Number, issues[1].Number}
	assert.ElementsMatch([]int{2, 3}, numbers)
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `go test ./internal/db/... -run TestListIssues_FilterByAssignee -v`
Expected: FAIL

- [ ] **Step 4: Update ListIssues to filter by assignee**

In `internal/db/queries.go`, find `ListIssues` (around line 3148) and add assignee filter:

```go
func (d *DB) ListIssues(
	ctx context.Context, opts ListIssuesOpts,
) ([]Issue, error) {
	// ... existing code ...

	if opts.Search != "" {
		cond, condArgs := listSearchCondition("i", opts.Search)
		conds = append(conds, cond)
		args = append(args, condArgs...)
	}

	// NEW: Assignee filter
	if opts.Assignee != "" {
		// JSON array contains the username (exact match within array)
		conds = append(conds, `i.assignees_json LIKE '%"' || ? || '"%'`)
		args = append(args, opts.Assignee)
	}

	// ... rest of function
```

- [ ] **Step 5: Run test to verify it passes**

Run: `go test ./internal/db/... -run TestListIssues_FilterByAssignee -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add internal/db/types.go internal/db/queries.go internal/db/queries_test.go
git commit -m "feat(db): add assignee filter to ListIssues"
```

---

### Task 9: Update ListIssues to populate Assignees field

**Files:**
- Modify: `internal/db/queries.go`
- Test: `internal/db/queries_test.go`

- [ ] **Step 1: Write failing test**

Add to `internal/db/queries_test.go`:

```go
func TestListIssues_PopulatesAssignees(t *testing.T) {
	require := require.New(t)
	d := openTestDB(t)
	ctx := t.Context()
	now := baseTime()
	repoID := insertTestRepo(t, d, "owner", "repo")

	issue := &db.Issue{
		RepoID:         repoID,
		PlatformID:     1,
		Number:         1,
		URL:            "https://github.com/owner/repo/issues/1",
		Title:          "Issue 1",
		Author:         "author",
		State:          "open",
		AssigneesJSON:  `["alice","bob"]`,
		CreatedAt:      now,
		UpdatedAt:      now,
		LastActivityAt: now,
	}
	_, err := d.UpsertIssue(ctx, issue)
	require.NoError(err)

	issues, err := d.ListIssues(ctx, db.ListIssuesOpts{State: "all"})
	require.NoError(err)
	require.Len(issues, 1)
	require.Equal([]string{"alice", "bob"}, issues[0].Assignees)
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./internal/db/... -run TestListIssues_PopulatesAssignees -v`
Expected: FAIL

- [ ] **Step 3: Update ListIssues query to select assignees_json and parse it**

In `internal/db/queries.go`, update the `ListIssues` query to include `assignees_json` in SELECT and parse after scanning:

```go
query := fmt.Sprintf(`
	SELECT i.id, i.repo_id, i.platform_id, i.platform_external_id, i.number, i.url, i.title,
	       i.author, i.state, i.body, i.comment_count, i.labels_json, i.assignees_json,
	       i.detail_fetched_at,
	       i.created_at, i.updated_at, i.last_activity_at, i.closed_at,
	       (s.number IS NOT NULL) AS starred
	FROM middleman_issues i
	// ... rest of query
```

And in the scan loop, parse the JSON:

```go
for rows.Next() {
	var issue Issue
	err := rows.Scan(
		&issue.ID, &issue.RepoID, &issue.PlatformID, &issue.PlatformExternalID,
		&issue.Number, &issue.URL, &issue.Title, &issue.Author, &issue.State,
		&issue.Body, &issue.CommentCount, &issue.LabelsJSON, &issue.AssigneesJSON,
		&issue.DetailFetchedAt,
		&issue.CreatedAt, &issue.UpdatedAt, &issue.LastActivityAt, &issue.ClosedAt,
		&issue.Starred,
	)
	if err != nil {
		return nil, err
	}
	// Parse assignees
	if issue.AssigneesJSON != "" && issue.AssigneesJSON != "[]" {
		_ = json.Unmarshal([]byte(issue.AssigneesJSON), &issue.Assignees)
	}
	issues = append(issues, issue)
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `go test ./internal/db/... -run TestListIssues_PopulatesAssignees -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add internal/db/queries.go internal/db/queries_test.go
git commit -m "feat(db): populate Assignees field in ListIssues"
```

---

### Task 10: Update API to accept assignee query param

**Files:**
- Modify: `internal/server/huma_routes.go`
- Test: `internal/server/api_test.go`

- [ ] **Step 1: Add Assignee field to listIssuesInput**

In `internal/server/huma_routes.go`, find `listIssuesInput` (around line 171) and add:

```go
type listIssuesInput struct {
	Repo     string `query:"repo"`
	State    string `query:"state"`
	Starred  bool   `query:"starred"`
	Q        string `query:"q"`
	Assignee string `query:"assignee"`  // NEW
	Limit    int    `query:"limit"`
	Offset   int    `query:"offset"`
}
```

- [ ] **Step 2: Write failing test**

Add to `internal/server/api_test.go`:

```go
func TestListIssues_FilterByAssignee(t *testing.T) {
	require := require.New(t)
	srv, d := newTestServer(t)
	ctx := t.Context()
	now := time.Now().UTC()
	repoID := insertTestRepo(t, d, "owner", "repo")

	// Insert issues with different assignees
	_, err := d.UpsertIssue(ctx, &db.Issue{
		RepoID: repoID, PlatformID: 1, Number: 1,
		URL: "https://github.com/owner/repo/issues/1",
		Title: "Issue 1", Author: "author", State: "open",
		AssigneesJSON: `["alice"]`,
		CreatedAt: now, UpdatedAt: now, LastActivityAt: now,
	})
	require.NoError(err)

	_, err = d.UpsertIssue(ctx, &db.Issue{
		RepoID: repoID, PlatformID: 2, Number: 2,
		URL: "https://github.com/owner/repo/issues/2",
		Title: "Issue 2", Author: "author", State: "open",
		AssigneesJSON: `["bob"]`,
		CreatedAt: now, UpdatedAt: now, LastActivityAt: now,
	})
	require.NoError(err)

	// Filter by alice
	resp := doJSON(t, srv, http.MethodGet, "/api/v1/issues?assignee=alice&state=all", nil)
	require.Equal(http.StatusOK, resp.Code)

	var issues []issueResponse
	require.NoError(json.Unmarshal(resp.Body.Bytes(), &issues))
	require.Len(issues, 1)
	require.Equal(1, issues[0].Number)
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `go test ./internal/server/... -run TestListIssues_FilterByAssignee -v`
Expected: FAIL

- [ ] **Step 4: Update listIssues handler to pass assignee to opts**

In `internal/server/huma_routes.go`, find `listIssues` function (around line 1735) and add:

```go
func (s *Server) listIssues(ctx context.Context, input *listIssuesInput) (*listIssuesOutput, error) {
	// ... existing validation ...

	opts := db.ListIssuesOpts{
		State:    input.State,
		Starred:  input.Starred,
		Search:   input.Q,
		Assignee: input.Assignee,  // NEW
		Limit:    input.Limit,
		Offset:   input.Offset,
	}
	// ... rest of function
```

- [ ] **Step 5: Run test to verify it passes**

Run: `go test ./internal/server/... -run TestListIssues_FilterByAssignee -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add internal/server/huma_routes.go internal/server/api_test.go
git commit -m "feat(api): add assignee query param to /issues endpoint"
```

---

### Task 11: Update issueResponse to include assignees

**Files:**
- Modify: `internal/server/api_types.go`
- Modify: `internal/server/huma_routes.go`

- [ ] **Step 1: Check issueResponse structure**

The `issueResponse` embeds `db.Issue`, so it should already include `Assignees` via the embedded struct. Verify by checking the JSON output in tests.

- [ ] **Step 2: Write test to verify assignees in API response**

Add to `internal/server/api_test.go`:

```go
func TestListIssues_ResponseIncludesAssignees(t *testing.T) {
	require := require.New(t)
	srv, d := newTestServer(t)
	ctx := t.Context()
	now := time.Now().UTC()
	repoID := insertTestRepo(t, d, "owner", "repo")

	_, err := d.UpsertIssue(ctx, &db.Issue{
		RepoID: repoID, PlatformID: 1, Number: 1,
		URL: "https://github.com/owner/repo/issues/1",
		Title: "Issue 1", Author: "author", State: "open",
		AssigneesJSON: `["alice","bob"]`,
		CreatedAt: now, UpdatedAt: now, LastActivityAt: now,
	})
	require.NoError(err)

	resp := doJSON(t, srv, http.MethodGet, "/api/v1/issues?state=all", nil)
	require.Equal(http.StatusOK, resp.Code)

	// Check raw JSON contains assignees
	body := resp.Body.String()
	require.Contains(body, `"assignees":["alice","bob"]`)
}
```

- [ ] **Step 3: Run test**

Run: `go test ./internal/server/... -run TestListIssues_ResponseIncludesAssignees -v`
Expected: PASS (if db.Issue already embeds correctly) or FAIL (if we need to add it)

- [ ] **Step 4: Commit if tests pass**

```bash
git add internal/server/api_test.go
git commit -m "test(api): verify assignees included in issue response"
```

---

### Task 12: Update frontend API types

**Files:**
- Modify: `packages/ui/src/api/types.ts` or regenerate from OpenAPI

- [ ] **Step 1: Check if types are auto-generated**

Run: `grep -r "assignees" packages/ui/src/api/`

If types are generated from OpenAPI, regenerate them:
Run: `make generate-api` or `bun run generate`

- [ ] **Step 2: Add Assignees to Issue type if manual**

If types are manual, add to the Issue type:

```typescript
export interface Issue {
  // ... existing fields ...
  assignees?: string[];
}
```

- [ ] **Step 3: Commit**

```bash
git add packages/ui/src/api/
git commit -m "feat(ui): add assignees to Issue type"
```

---

### Task 13: Display assignees in IssueDetail.svelte

**Files:**
- Modify: `packages/ui/src/components/detail/IssueDetail.svelte`

- [ ] **Step 1: Add assignees display after Author in meta-row**

In `packages/ui/src/components/detail/IssueDetail.svelte`, find the meta-row section (around line 855) and add assignees display:

```svelte
<div class="meta-row">
  <span class="meta-item">{detail.repo_owner}/{detail.repo_name}</span>
  <span class="meta-sep">·</span>
  <CopyItemNumber kind="issue" number={issue.Number} url={issue.URL} />
  <span class="meta-sep">·</span>
  <span class="meta-item">{issue.Author}</span>
  {#if issue.assignees && issue.assignees.length > 0}
    <span class="meta-sep">·</span>
    <span class="meta-item">
      Assigned: {issue.assignees.join(", ")}
    </span>
  {/if}
  <span class="meta-sep">·</span>
  <span class="meta-item">{timeAgo(issue.CreatedAt)}</span>
  <span class="meta-sep">·</span>
  <Chip size="sm" class={`issue-state-chip chip--${issue.State}`}>
    {issue.State === "open" ? "Open" : "Closed"}
  </Chip>
</div>
```

- [ ] **Step 2: Run frontend dev server and verify**

Run: `bun run dev`
Navigate to an issue and verify assignees display

- [ ] **Step 3: Commit**

```bash
git add packages/ui/src/components/detail/IssueDetail.svelte
git commit -m "feat(ui): display assignees in issue detail view"
```

---

### Task 14: Integration test

**Files:**
- Test: Run full test suite

- [ ] **Step 1: Run all Go tests**

Run: `go test ./...`
Expected: All tests pass

- [ ] **Step 2: Run frontend tests**

Run: `bun test`
Expected: All tests pass

- [ ] **Step 3: Manual E2E test**

1. Start middleman: `go run ./cmd/middleman`
2. Open UI: `open http://localhost:8091`
3. Navigate to an issue
4. Verify assignees display (may need to sync a repo with assigned issues)

- [ ] **Step 4: Commit any fixes**

If any issues found, fix and commit.

---

### Task 15: Final commit and PR

- [ ] **Step 1: Review all changes**

Run: `git log --oneline origin/main..HEAD`
Review commit history

- [ ] **Step 2: Push branch**

```bash
git push -u origin feat/issue-assignees
```

- [ ] **Step 3: Create PR**

```bash
gh pr create --title "feat: add assignee tracking to issues" --body "$(cat <<'EOF'
## Summary

Add assignee tracking to middleman issues to support nd-triage filtering by assigned user.

## Changes

- Database: Add `assignees_json` column to `middleman_issues`
- Sync: Extract assignees from GitHub/GitLab API during issue sync
- API: Add `?assignee=` filter to `GET /api/v1/issues`
- UI: Display assignees in issue detail view

## Test Plan

- [x] Unit tests for assignee extraction in GitHub normalize
- [x] Unit tests for assignee extraction in GitLab normalize
- [x] Unit tests for assignee filter in ListIssues
- [x] API test for assignee query param
- [x] Manual verification of UI display
EOF
)"
```
