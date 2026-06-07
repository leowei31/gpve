-- Vector nearest-neighbour retrieval.
create or replace function match_games(
  query_embedding vector(768),
  match_count int default 25,
  exclude_id bigint default null
)
returns table (id bigint, title text, similarity float)
language sql stable as $$
  select g.id, g.title, 1 - (g.embedding <=> query_embedding) as similarity
  from games g
  where g.embedding is not null
    and (exclude_id is null or g.id <> exclude_id)
  order by g.embedding <=> query_embedding
  limit match_count;
$$;
