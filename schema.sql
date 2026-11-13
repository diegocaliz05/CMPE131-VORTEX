CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clubs (
    club_id INTEGER PRIMARY KEY AUTOINCREMENT,
    club_name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS memberships (
    membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    club_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (club_id) REFERENCES clubs(club_id)
);

CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id INTEGER NOT NULL,
    event_name TEXT NOT NULL,
    description TEXT,
    event_date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    location TEXT,
    status TEXT NOT NULL,
    FOREIGN KEY (club_id) REFERENCES clubs(club_id)
);

CREATE TABLE IF NOT EXISTS notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event_id INTEGER,
    message TEXT NOT NULL,
    read_status INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (event_id) REFERENCES events(event_id)
);

-- Added for architecture: integrity guarantees behind the service-layer checks
-- (FR-14 duplicate prevention; one membership row per user/club pair).
CREATE UNIQUE INDEX IF NOT EXISTS idx_memberships_user_club
    ON memberships(user_id, club_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_events_no_duplicates
    ON events(club_id, event_name, event_date, start_time, end_time)
    WHERE status != 'cancelled';
CREATE INDEX IF NOT EXISTS idx_events_date ON events(event_date, status);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, read_status);
