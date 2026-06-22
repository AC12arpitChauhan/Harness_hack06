-- PR Health Analytics — schema reference (generated from app/persistence/orm.py).
-- Rendered with the SQLite dialect; the same portable types (JSON/Text/etc.)
-- apply to PostgreSQL. Alembic (alembic/versions/) is authoritative for prod.


CREATE TABLE repositories (
	id VARCHAR(36) NOT NULL, 
	provider VARCHAR(32) NOT NULL, 
	provider_id VARCHAR(255) NOT NULL, 
	name VARCHAR(512) NOT NULL, 
	url TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_repo_provider_id UNIQUE (provider, provider_id)
);

CREATE INDEX ix_repositories_provider ON repositories (provider);

CREATE TABLE pull_requests (
	id VARCHAR(36) NOT NULL, 
	repo_id VARCHAR(36) NOT NULL, 
	provider VARCHAR(32) NOT NULL, 
	provider_pr_id VARCHAR(255) NOT NULL, 
	title TEXT NOT NULL, 
	description TEXT NOT NULL, 
	author VARCHAR(255) NOT NULL, 
	state VARCHAR(32) NOT NULL, 
	opened_at DATETIME, 
	merged_at DATETIME, 
	closed_at DATETIME, 
	source_branch VARCHAR(512) NOT NULL, 
	target_branch VARCHAR(512) NOT NULL, 
	commit_sha VARCHAR(64) NOT NULL, 
	base_commit_sha VARCHAR(64) NOT NULL, 
	jira_issue_id VARCHAR(64), 
	override_reason TEXT, 
	override_approved_by VARCHAR(255), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_pr_repo_provider_pr_id UNIQUE (repo_id, provider_pr_id), 
	FOREIGN KEY(repo_id) REFERENCES repositories (id)
);

CREATE INDEX ix_pull_requests_merged_at ON pull_requests (merged_at);
CREATE INDEX ix_pull_requests_state ON pull_requests (state);
CREATE INDEX ix_pull_requests_author ON pull_requests (author);
CREATE INDEX ix_pr_repo_state ON pull_requests (repo_id, state);
CREATE INDEX ix_pull_requests_provider ON pull_requests (provider);
CREATE INDEX ix_pull_requests_repo_id ON pull_requests (repo_id);

CREATE TABLE repository_metrics (
	id VARCHAR(36) NOT NULL, 
	repo_id VARCHAR(36) NOT NULL, 
	period_start DATETIME NOT NULL, 
	period_end DATETIME NOT NULL, 
	pr_count INTEGER NOT NULL, 
	avg_health_score FLOAT NOT NULL, 
	median_merge_time_minutes FLOAT NOT NULL, 
	review_skipped_rate FLOAT NOT NULL, 
	ci_failure_rate FLOAT NOT NULL, 
	avg_review_quality_score FLOAT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_metric_repo_period UNIQUE (repo_id, period_start), 
	FOREIGN KEY(repo_id) REFERENCES repositories (id)
);

CREATE INDEX ix_repository_metrics_repo_id ON repository_metrics (repo_id);

CREATE TABLE analysis_runs (
	id VARCHAR(36) NOT NULL, 
	pr_id VARCHAR(36) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	started_at DATETIME, 
	completed_at DATETIME, 
	error_message TEXT, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(pr_id) REFERENCES pull_requests (id)
);

CREATE INDEX ix_analysis_runs_pr_id ON analysis_runs (pr_id);

CREATE TABLE pr_checks (
	id VARCHAR(36) NOT NULL, 
	pr_id VARCHAR(36) NOT NULL, 
	check_name VARCHAR(255) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	completed_at DATETIME, 
	url TEXT, 
	metadata_json JSON NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(pr_id) REFERENCES pull_requests (id)
);

CREATE INDEX ix_pr_checks_pr_id ON pr_checks (pr_id);

CREATE TABLE pr_diffs (
	id VARCHAR(36) NOT NULL, 
	pr_id VARCHAR(36) NOT NULL, 
	files_changed INTEGER NOT NULL, 
	additions INTEGER NOT NULL, 
	deletions INTEGER NOT NULL, 
	files_json JSON NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(pr_id) REFERENCES pull_requests (id)
);

CREATE UNIQUE INDEX ix_pr_diffs_pr_id ON pr_diffs (pr_id);

CREATE TABLE pr_reviews (
	id VARCHAR(36) NOT NULL, 
	pr_id VARCHAR(36) NOT NULL, 
	reviewer VARCHAR(255) NOT NULL, 
	state VARCHAR(32) NOT NULL, 
	submitted_at DATETIME, 
	lines_commented INTEGER NOT NULL, 
	metadata_json JSON NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(pr_id) REFERENCES pull_requests (id)
);

CREATE INDEX ix_pr_reviews_pr_id ON pr_reviews (pr_id);

CREATE TABLE analysis_scores (
	id VARCHAR(36) NOT NULL, 
	analysis_run_id VARCHAR(36) NOT NULL, 
	pr_id VARCHAR(36) NOT NULL, 
	health_score FLOAT NOT NULL, 
	risk_score FLOAT NOT NULL, 
	review_quality_score FLOAT NOT NULL, 
	merge_readiness FLOAT NOT NULL, 
	score_breakdown_json JSON NOT NULL, 
	blocking_reason TEXT, 
	computed_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(analysis_run_id) REFERENCES analysis_runs (id), 
	FOREIGN KEY(pr_id) REFERENCES pull_requests (id)
);

CREATE INDEX ix_analysis_scores_pr_id ON analysis_scores (pr_id);
CREATE UNIQUE INDEX ix_analysis_scores_analysis_run_id ON analysis_scores (analysis_run_id);

CREATE TABLE analysis_signals (
	id VARCHAR(36) NOT NULL, 
	analysis_run_id VARCHAR(36) NOT NULL, 
	signal_name VARCHAR(128) NOT NULL, 
	severity VARCHAR(32) NOT NULL, 
	value FLOAT, 
	threshold FLOAT, 
	exceeds_threshold BOOLEAN NOT NULL, 
	explanation TEXT NOT NULL, 
	metadata_json JSON NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(analysis_run_id) REFERENCES analysis_runs (id)
);

CREATE INDEX ix_analysis_signals_analysis_run_id ON analysis_signals (analysis_run_id);
CREATE INDEX ix_analysis_signals_signal_name ON analysis_signals (signal_name);

CREATE TABLE pr_narratives (
	id VARCHAR(36) NOT NULL, 
	pr_id VARCHAR(36) NOT NULL, 
	analysis_run_id VARCHAR(36) NOT NULL, 
	ai_summary TEXT NOT NULL, 
	ai_recommendation TEXT NOT NULL, 
	ai_model VARCHAR(64) NOT NULL, 
	posted_at DATETIME, 
	was_accurate BOOLEAN, 
	feedback_explanation TEXT, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(pr_id) REFERENCES pull_requests (id), 
	FOREIGN KEY(analysis_run_id) REFERENCES analysis_runs (id)
);

CREATE UNIQUE INDEX ix_pr_narratives_pr_id ON pr_narratives (pr_id);
