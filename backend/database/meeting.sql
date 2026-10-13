CREATE TABLE IF NOT EXISTS meetings (
    meeting_id UUID PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    meeting_url TEXT NOT NULL,
    platform VARCHAR(32) NOT NULL,
    bot_id VARCHAR(64) UNIQUE,
    bot_state VARCHAR(64),
    status VARCHAR(32) NOT NULL,
    recipient_email VARCHAR(320),
    join_at TIMESTAMPTZ,
    minutes JSONB,
    email_status VARCHAR(32) NOT NULL,
    email_sent_to VARCHAR(320),
    error_message TEXT,
    ended_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_meetings_status ON meetings (status);

CREATE TABLE IF NOT EXISTS meeting_utterances (
    meeting_utterance_id UUID PRIMARY KEY,
    meeting_id UUID NOT NULL REFERENCES meetings (meeting_id) ON DELETE CASCADE,
    speaker_name VARCHAR(255) NOT NULL,
    speaker_uuid VARCHAR(128) NOT NULL,
    speaker_user_uuid VARCHAR(128),
    speaker_is_host BOOLEAN NOT NULL DEFAULT FALSE,
    timestamp_ms BIGINT NOT NULL,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    text TEXT NOT NULL,
    source VARCHAR(16) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (meeting_id, speaker_uuid, timestamp_ms)
);

CREATE INDEX IF NOT EXISTS idx_meeting_utterances_meeting_ts ON meeting_utterances (meeting_id, timestamp_ms);

CREATE TABLE IF NOT EXISTS attendee_webhook_events (
    attendee_webhook_event_id UUID PRIMARY KEY,
    idempotency_key UUID NOT NULL UNIQUE,
    bot_id VARCHAR(64),
    trigger_type VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
