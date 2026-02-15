-- Briefing tables for daily finance summary + TTS
-- Created: 2026-02-10

create table if not exists wsj_briefings (
  id uuid default gen_random_uuid() primary key,
  date date not null,
  category text not null default 'ALL',
  briefing_text text not null,
  audio_url text,
  audio_duration integer,
  item_count integer not null default 0,
  model text,
  tts_provider text,
  created_at timestamptz default now()
);

create unique index idx_briefings_date_category on wsj_briefings(date, category);

create table if not exists wsj_briefing_items (
  briefing_id uuid not null references wsj_briefings(id) on delete cascade,
  wsj_item_id uuid not null references wsj_items(id) on delete cascade,
  primary key (briefing_id, wsj_item_id)
);

create index idx_briefing_items_wsj on wsj_briefing_items(wsj_item_id);
