-- Captured at: 2026-02-01T00:00:00Z
-- Scope: complete profile tables; subject lookup old@example.test
CREATE TABLE customer_profiles_primary (resource_id TEXT, user_id TEXT, email TEXT, updated_at TEXT);
INSERT INTO customer_profiles_primary VALUES ('account_decoy','user_other','old.extra@example.test','2026-01-01T00:00:00Z');
CREATE TABLE customer_profiles_failover_replica (resource_id TEXT, user_id TEXT, email TEXT, updated_at TEXT);
INSERT INTO customer_profiles_failover_replica VALUES ('account_decoy','user_other','old.extra@example.test','2026-01-01T00:00:00Z');
INSERT INTO customer_profiles_failover_replica VALUES ('account_target','user_target','old@example.test','2026-01-01T00:00:00Z');
