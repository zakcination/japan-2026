-- Group planning, stage 1. Paste into Supabase → SQL Editor → Run. Idempotent.
create extension if not exists pgcrypto with schema extensions;

create table if not exists public.trips (id text primary key, name text not null);
create table if not exists public.members (
  id uuid primary key default gen_random_uuid(), trip text not null references public.trips(id),
  name text not null check (length(name) between 1 and 40), role text not null check (role in ('host','guest')),
  pin_hash text, fails int not null default 0, locked_until timestamptz);
-- one-time invite code for a guest's first sign-in (the ids are visible to «Кто вы?», so an id alone must not be enough)
alter table public.members add column if not exists invite text;
create table if not exists public.member_devices (
  uid uuid primary key, member uuid not null references public.members(id) on delete cascade, at timestamptz default now());
create table if not exists public.plan (trip text primary key references public.trips(id), doc jsonb not null, version int not null default 1);
create table if not exists public.parts (trip text references public.trips(id), id text, part jsonb not null, primary key (trip, id));
create table if not exists public.joins (member uuid references public.members(id) on delete cascade, scope text check (scope in ('part','day','stop','mine')),
  ref text, mode text check (mode in ('in','out')), primary key (member, scope, ref));
create table if not exists public.recipes (trip text references public.trips(id), bk text, r jsonb not null, primary key (trip, bk));
create table if not exists public.tasks (trip text references public.trips(id), id text, t jsonb not null, assignee uuid, primary key (trip, id));
create table if not exists public.task_state (member uuid references public.members(id) on delete cascade, ref text, done boolean, at timestamptz default now(), primary key (member, ref));
create table if not exists public.attachments (id text primary key, member uuid references public.members(id) on delete cascade, a jsonb not null, shared boolean not null default false);
create table if not exists public.my_stops (id text primary key, member uuid references public.members(id) on delete cascade, s jsonb not null, shared boolean not null default false);
create table if not exists public.my_bookings (id text primary key, member uuid references public.members(id) on delete cascade, b jsonb not null);

alter table public.trips enable row level security;
alter table public.members enable row level security;
alter table public.member_devices enable row level security;
alter table public.plan enable row level security;
alter table public.parts enable row level security;
alter table public.joins enable row level security;
alter table public.recipes enable row level security;
alter table public.tasks enable row level security;
alter table public.task_state enable row level security;
alter table public.attachments enable row level security;
alter table public.my_stops enable row level security;
alter table public.my_bookings enable row level security;
-- no policies on tables: the only way in is the functions below

create or replace function public._me() returns public.members language plpgsql stable security definer
set search_path = public, extensions as $$
declare m public.members;
begin
  select mm.* into m from public.member_devices d join public.members mm on mm.id = d.member where d.uid = auth.uid();
  if m.id is null then raise exception 'not a member' using errcode = 'P0001'; end if;
  return m;
end $$;

create or replace function public._host() returns public.members language plpgsql stable security definer
set search_path = public, extensions as $$
declare m public.members := public._me();
begin
  if m.role <> 'host' then raise exception 'host only' using errcode = 'P0001'; end if;
  return m;
end $$;

create or replace function public._https(u text) returns void language plpgsql immutable as $$
begin
  if u is not null and u <> '' and u !~ '^https://[^\s"''<>]+$' then raise exception 'links must be https' using errcode = 'P0001'; end if;
end $$;

-- Storage RLS policies below run as the calling ("authenticated") role, not as the table owner, so a
-- direct policy query against member_devices/attachments/members (RLS-enabled, no policies) would always
-- see zero rows and deny everything. These two helpers are security definer (run as the owner, who bypasses
-- RLS on tables it owns) so the policies can call them instead of querying the tables directly.
create or replace function public._device_member() returns text language sql stable security definer
set search_path = public, extensions as $$
  select member::text from public.member_devices where uid = auth.uid();
$$;

create or replace function public._can_read_ticket(p_name text) returns boolean language sql stable security definer
set search_path = public, extensions as $$
  select (storage.foldername(p_name))[1] = public._device_member()
    or exists (select 1 from public.attachments a where a.shared and a.a->>'kind' = 'file' and a.a->>'path' = p_name
               and (storage.foldername(p_name))[1] = a.member::text
               and a.member in (select id from public.members where trip = (
                 select mm.trip from public.member_devices d join public.members mm on mm.id = d.member where d.uid = auth.uid())));
$$;

drop function if exists public.claim_member(uuid, text);
create or replace function public.claim_member(p_member uuid, p_pin text, p_code text default null) returns jsonb language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members; already uuid;
begin
  if auth.uid() is null then raise exception 'sign in first' using errcode = 'P0001'; end if;
  select * into m from public.members where id = p_member for update;
  if m.id is null then raise exception 'no such member' using errcode = 'P0001'; end if;
  if m.locked_until is not null and m.locked_until > now() then raise exception 'locked, try later' using errcode = 'P0001'; end if;
  if p_pin is null or p_pin !~ '^[0-9]{4}$' then raise exception 'PIN must be 4 digits' using errcode = 'P0001'; end if;
  if m.pin_hash is null then
    -- first claim of a PIN-less member: only a guest slot, and only from a device not already bound
    -- to someone else on this trip (a claimed member's device cannot also take over a fresh slot).
    if m.role <> 'guest' then raise exception 'PIN is set by the owner' using errcode = 'P0001'; end if;
    select d.member into already from public.member_devices d join public.members mm on mm.id = d.member
      where d.uid = auth.uid() and mm.trip = m.trip and d.member <> m.id;
    if already is not null then raise exception 'ask a host' using errcode = 'P0001'; end if;
    if m.invite is null or p_code is distinct from m.invite then
      update public.members set fails = case when fails + 1 >= 5 then 0 else fails + 1 end,
        locked_until = case when fails + 1 >= 5 then now() + interval '15 minutes' else locked_until end where id = m.id;
      return jsonb_build_object('error', 'invite needed');   -- committed, like a wrong PIN
    end if;
    update public.members set pin_hash = crypt(p_pin, gen_salt('bf')), fails = 0, invite = null where id = m.id;
  elsif m.pin_hash is distinct from crypt(p_pin, m.pin_hash) then
    update public.members set fails = case when fails + 1 >= 5 then 0 else fails + 1 end,
      locked_until = case when fails + 1 >= 5 then now() + interval '15 minutes' else locked_until end where id = m.id;
    return jsonb_build_object('error', 'wrong PIN');   -- committed; the app shows it
  else
    update public.members set fails = 0 where id = m.id;
  end if;
  delete from public.member_devices where member = m.id and uid not in (
    select uid from public.member_devices where member = m.id order by at desc limit 2);
  insert into public.member_devices(uid, member) values (auth.uid(), m.id)
    on conflict (uid) do update set member = excluded.member, at = now();
  return jsonb_build_object('id', m.id, 'name', m.name, 'role', m.role);
end $$;
-- NOTE: a raised exception would roll back the fail counter, so a wrong PIN returns {"error": "wrong PIN"}.
-- The fake raises instead; group_contract treats both as an error (see Step 4).

-- names for the «Кто вы?» sheet: any signed-in session (anonymous included) may read ids and names only
create or replace function public.member_names(p_trip text) returns jsonb language plpgsql stable security definer
set search_path = public, extensions as $$
begin
  if auth.uid() is null then raise exception 'sign in first' using errcode = 'P0001'; end if;
  return coalesce((select jsonb_agg(jsonb_build_object('id', id, 'name', name) order by name) from public.members where trip = p_trip), '[]');
end $$;

create or replace function public.group_state(p_trip text) returns jsonb language plpgsql stable security definer
set search_path = public, extensions as $$
declare m public.members := public._me();
begin
  if m.trip is distinct from p_trip then raise exception 'not a member' using errcode = 'P0001'; end if;
  return jsonb_build_object(
    'me', jsonb_build_object('id', m.id, 'name', m.name, 'role', m.role),
    'trip', (select to_jsonb(t) from public.trips t where t.id = p_trip),
    'plan', (select jsonb_build_object('doc', doc, 'version', version) from public.plan where trip = p_trip),
    'members', coalesce((select jsonb_agg(jsonb_build_object('id', id, 'name', name, 'role', role)) from public.members where trip = p_trip), '[]'),
    'parts', coalesce((select jsonb_agg(part) from public.parts where trip = p_trip), '[]'),
    'joins', coalesce((select jsonb_agg(jsonb_build_object('member', j.member, 'scope', j.scope, 'ref', j.ref, 'mode', j.mode))
                       from public.joins j join public.members x on x.id = j.member where x.trip = p_trip), '[]'),
    'recipes', coalesce((select jsonb_agg(r) from public.recipes where trip = p_trip), '[]'),
    'tasks', coalesce((select jsonb_agg(t || jsonb_build_object('assignee', assignee)) from public.tasks where trip = p_trip and (assignee is null or assignee = m.id)), '[]'),
    'my_stops', coalesce((select jsonb_agg(s || jsonb_build_object('member', s2.member, 'shared', s2.shared)) from public.my_stops s2
                          join public.members x on x.id = s2.member where x.trip = p_trip and (s2.member = m.id or s2.shared)), '[]'),
    'my_bookings', coalesce((select jsonb_agg(b || jsonb_build_object('member', member)) from public.my_bookings where member = m.id), '[]'),
    'task_state', coalesce((select jsonb_agg(jsonb_build_object('ref', ref, 'done', done, 'at', at)) from public.task_state where member = m.id), '[]'),
    'attachments', coalesce((select jsonb_agg(a || jsonb_build_object('member', a2.member, 'shared', a2.shared)) from public.attachments a2
                             join public.members x on x.id = a2.member where x.trip = p_trip and (a2.member = m.id or a2.shared)), '[]'),
    'now', now());
end $$;

create or replace function public.set_join(p_scope text, p_ref text, p_mode text) returns boolean language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._me();
begin
  if p_mode = 'none' then delete from public.joins where member = m.id and scope = p_scope and ref = p_ref; return true; end if;
  insert into public.joins values (m.id, p_scope, p_ref, p_mode) on conflict (member, scope, ref) do update set mode = excluded.mode;
  return true;
end $$;

create or replace function public.save_my_stop(p_stop jsonb) returns boolean language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._me(); owner uuid;
begin
  if p_stop->>'id' is null or (p_stop->>'id') !~ '^m-[A-Za-z0-9-]{1,60}$' then raise exception 'bad id' using errcode = 'P0001'; end if;
  select member into owner from public.my_stops where id = p_stop->>'id';
  if owner is not null and owner <> m.id then raise exception 'not yours' using errcode = 'P0001'; end if;
  insert into public.my_stops values (p_stop->>'id', m.id, p_stop - 'shared' - 'member', coalesce((p_stop->>'shared')::boolean, false))
    on conflict (id) do update set s = excluded.s, shared = excluded.shared;
  return true;
end $$;

create or replace function public.delete_my_stop(p_id text) returns boolean language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._me();
begin delete from public.my_stops where id = p_id and member = m.id; return true; end $$;

create or replace function public.save_my_booking(p_b jsonb) returns boolean language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._me();
begin
  if p_b->>'id' is null or (p_b->>'id') !~ '^mb-[A-Za-z0-9-]{1,60}$' then raise exception 'bad id' using errcode = 'P0001'; end if;
  perform public._https(p_b->>'url');
  insert into public.my_bookings values (p_b->>'id', m.id, p_b - 'member')
    on conflict (id) do update set b = excluded.b where public.my_bookings.member = m.id;
  return true;
end $$;

create or replace function public.set_task_state(p_ref text, p_done boolean) returns boolean language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._me();
begin
  insert into public.task_state values (m.id, p_ref, p_done, now()) on conflict (member, ref) do update set done = excluded.done, at = now();
  return true;
end $$;

create or replace function public.save_attachment(p_a jsonb) returns boolean language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._me(); owner uuid; body jsonb;
begin
  if coalesce(p_a->>'kind','') not in ('file','link') then raise exception 'bad kind' using errcode = 'P0001'; end if;
  perform public._https(p_a->>'url');   -- run regardless of kind: a crafted 'file' with a javascript: url must not slip through
  if (p_a->>'kind') = 'file' then
    if coalesce(p_a->>'path','') not like m.id::text || '/%' then raise exception 'not your file' using errcode = 'P0001'; end if;
    body := p_a - 'shared' - 'member';
  else
    body := p_a - 'shared' - 'member' - 'path';   -- a link never stores a path: it cannot be used to point at another member's file
  end if;
  select member into owner from public.attachments where id = p_a->>'id';
  if owner is not null and owner <> m.id then raise exception 'not yours' using errcode = 'P0001'; end if;
  insert into public.attachments values (p_a->>'id', m.id, body, coalesce((p_a->>'shared')::boolean, false))
    on conflict (id) do update set a = excluded.a, shared = excluded.shared;
  return true;
end $$;

create or replace function public.delete_attachment(p_id text) returns boolean language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._me();
begin delete from public.attachments where id = p_id and member = m.id; return true; end $$;

create or replace function public.save_plan(p_doc jsonb, p_version int) returns int language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._host(); v int;
begin
  update public.plan set doc = p_doc, version = version + 1 where trip = m.trip and version = p_version returning version into v;
  if v is null then raise exception 'plan version changed' using errcode = 'P0001'; end if;
  return v;
end $$;

create or replace function public.save_part(p_part jsonb) returns boolean language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._host();
begin
  insert into public.parts values (m.trip, p_part->>'id', p_part) on conflict (trip, id) do update set part = excluded.part;
  return true;
end $$;

create or replace function public.save_recipe(p_r jsonb) returns boolean language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._host();
begin
  perform public._https(p_r->>'url');
  insert into public.recipes values (m.trip, p_r->>'bk', p_r) on conflict (trip, bk) do update set r = excluded.r;
  return true;
end $$;

create or replace function public.add_member(p_name text, p_role text) returns jsonb language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._host(); i uuid; c text := encode(gen_random_bytes(6), 'hex');
begin
  insert into public.members(trip, name, role, invite) values (m.trip, trim(p_name), p_role, case when p_role = 'guest' then c end) returning id into i;
  return jsonb_build_object('id', i, 'code', case when p_role = 'guest' then c end);
end $$;

drop function if exists public.reset_pin(uuid);
create or replace function public.reset_pin(p_member uuid) returns jsonb language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._host(); c text := encode(gen_random_bytes(6), 'hex');
begin
  update public.members set pin_hash = null, fails = 0, locked_until = null,
    invite = case when role = 'guest' then c end where id = p_member and trip = m.trip;
  return jsonb_build_object('code', c);
end $$;

create or replace function public.save_task(p_task jsonb) returns text language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._host(); i text := coalesce(p_task->>'id', 't-' || gen_random_uuid());
begin
  perform public._https(p_task->>'url');
  insert into public.tasks values (m.trip, i, p_task - 'assignee', nullif(p_task->>'assignee','')::uuid)
    on conflict (trip, id) do update set t = excluded.t, assignee = excluded.assignee;
  return i;
end $$;

create or replace function public.import_tasks(p_tasks jsonb) returns int language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._host(); x jsonb; n int := 0;
begin
  for x in select * from jsonb_array_elements(p_tasks) loop perform public.save_task(x); n := n + 1; end loop;
  return n;
end $$;

-- Task 10a: invite links for guests already added, and a private activation funnel (counts only, never who)
create or replace function public.invite_link(p_member uuid) returns jsonb language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._host(); g public.members;
begin
  select * into g from public.members where id = p_member and trip = m.trip;
  if g.id is null then raise exception 'no such member' using errcode = 'P0001'; end if;
  if g.role <> 'guest' or g.pin_hash is not null then return jsonb_build_object('code', null); end if;
  if g.invite is null then
    update public.members set invite = encode(gen_random_bytes(6), 'hex') where id = g.id returning invite into g.invite;
  end if;
  return jsonb_build_object('code', g.invite);
end $$;

create table if not exists public.member_events (member uuid references public.members(id) on delete cascade,
  event text check (event in ('login','installed','joined','bought')), at timestamptz default now(), primary key (member, event));
alter table public.member_events enable row level security;

create or replace function public.track(p_event text) returns boolean language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._me();
begin
  if p_event is null or p_event not in ('login','installed','joined','bought') then raise exception 'bad event' using errcode = 'P0001'; end if;
  insert into public.member_events(member, event) values (m.id, p_event) on conflict do nothing;
  return true;
end $$;

create or replace function public.funnel_counts() returns jsonb language plpgsql stable security definer
set search_path = public, extensions as $$
declare m public.members := public._host();
begin
  return (select jsonb_build_object(
    'members', (select count(*) from public.members where trip = m.trip),
    'login', count(*) filter (where e.event = 'login'), 'installed', count(*) filter (where e.event = 'installed'),
    'joined', count(*) filter (where e.event = 'joined'), 'bought', count(*) filter (where e.event = 'bought'))
    from public.member_events e join public.members x on x.id = e.member where x.trip = m.trip);
end $$;

-- Deny-by-default: revoke the implicit grants Postgres/Supabase hand out on function creation (to PUBLIC,
-- and Supabase's own default privileges additionally grant to anon/authenticated), then grant back only
-- the RPCs the app calls plus the two storage helpers above.
revoke all on all functions in schema public from public, anon, authenticated;
grant execute on function public.member_names, public.group_state, public.claim_member(uuid, text, text), public.set_join, public.save_my_stop, public.delete_my_stop,
  public.save_my_booking, public.set_task_state, public.save_attachment, public.delete_attachment, public.save_plan,
  public.save_part, public.save_recipe, public.add_member, public.reset_pin, public.save_task, public.import_tasks, public.invite_link, public.track, public.funnel_counts,
  public._device_member, public._can_read_ticket to authenticated;

-- storage: private bucket; a member writes only into <member id>/...; reads own files and files of shared attachments
insert into storage.buckets (id, name, public) values ('tickets', 'tickets', false) on conflict (id) do nothing;
drop policy if exists "tickets write own" on storage.objects;
create policy "tickets write own" on storage.objects for insert to authenticated
  with check (bucket_id = 'tickets' and (storage.foldername(name))[1] = public._device_member());
drop policy if exists "tickets delete own" on storage.objects;
create policy "tickets delete own" on storage.objects for delete to authenticated
  using (bucket_id = 'tickets' and (storage.foldername(name))[1] = public._device_member());
drop policy if exists "tickets read own or shared" on storage.objects;
create policy "tickets read own or shared" on storage.objects for select to authenticated
  using (bucket_id = 'tickets' and public._can_read_ticket(name));

-- Hosts' PINs are set at trip setup by the owner, here in the SQL editor — claim_member refuses to set
-- a PIN-less host's PIN from the app (see claim_member's 'PIN is set by the owner'). Example:
-- update public.members set pin_hash = crypt('1234', gen_salt('bf')) where trip = 'miras-aikosh' and name = 'Айкош';
