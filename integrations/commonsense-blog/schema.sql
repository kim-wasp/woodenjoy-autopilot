-- 커먼센스 블로그용 표와 사진 저장소 (Supabase → SQL Editor 에 붙여넣고 Run)
-- 글은 스튜디오(GitHub Actions)가 service_role 키로 넣고, 앱의 /blog 페이지는 공개 글만 읽어요.

create table if not exists public.posts (
  id            bigint generated always as identity primary key,
  slug          text not null unique,
  title         text not null,
  description   text,
  content_html  text not null,
  content_md    text,
  hero_url      text,
  keywords      text[] default '{}',
  sources       jsonb default '[]'::jsonb,
  category      text,
  status        text not null default 'published' check (status in ('published','draft','hidden')),
  published_at  timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index if not exists posts_published_idx on public.posts (status, published_at desc);

alter table public.posts enable row level security;
drop policy if exists "공개 글 읽기" on public.posts;
create policy "공개 글 읽기" on public.posts for select using (status = 'published');
-- 쓰기 정책은 만들지 않아요: service_role 키(스튜디오)만 쓸 수 있어요.

-- 사진 저장소 (공개 읽기)
insert into storage.buckets (id, name, public) values ('blog', 'blog', true)
on conflict (id) do update set public = true;
