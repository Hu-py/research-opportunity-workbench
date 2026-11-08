-- Business Workspace Agent: resource-bound OAuth audience hook
-- Run once in Supabase SQL Editor as the project owner (postgres).
-- This does NOT change the active JWT signing key and does NOT register a
-- Supabase Auth hook automatically. Complete the Dashboard steps in
-- docs/BUSINESS_MCP_OAUTH_SETUP.md after running this SQL.

create schema if not exists business_agent_private;

revoke all on schema business_agent_private from public, anon, authenticated, service_role;

create table if not exists business_agent_private.oauth_clients (
    client_id text primary key,
    audience text not null
        check (audience = 'https://research-atlas-api-test.onrender.com/research-advisor/mcp'),
    enabled boolean not null default true,
    created_at timestamptz not null default now()
);

alter table business_agent_private.oauth_clients enable row level security;

revoke all on table business_agent_private.oauth_clients
    from public, anon, authenticated, service_role;

create or replace function public.business_agent_oauth_access_token_hook(event jsonb)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
    claims jsonb := coalesce(event->'claims', '{}'::jsonb);
    oauth_client_id text := claims->>'client_id';
    resource_audience text;
begin
    -- Ordinary Supabase sign-ins have no OAuth client_id and remain unchanged.
    -- Only explicitly registered Business MCP OAuth clients receive the
    -- resource-bound audience. Unknown or disabled clients are not modified.
    if oauth_client_id is not null then
        select c.audience
          into resource_audience
          from business_agent_private.oauth_clients as c
         where c.client_id = oauth_client_id
           and c.enabled = true;

        if resource_audience is not null then
            -- Preserve Supabase's authenticated audience for compatibility
            -- while also binding the token to this exact MCP resource.
            claims := jsonb_set(
                claims,
                '{aud}',
                jsonb_build_array(resource_audience, 'authenticated'),
                true
            );
        end if;
    end if;

    return jsonb_build_object('claims', claims);
end;
$$;

revoke all on function public.business_agent_oauth_access_token_hook(jsonb)
    from public, anon, authenticated, service_role;

grant execute on function public.business_agent_oauth_access_token_hook(jsonb)
    to supabase_auth_admin;

comment on function public.business_agent_oauth_access_token_hook(jsonb) is
    'Binds approved Business Workspace Agent OAuth client tokens to the Render Research Advisor MCP resource.';

-- After ChatGPT DCR has created the OAuth client, replace the placeholder
-- below with the exact client_id from Supabase Authentication > OAuth Apps.
-- Then run this INSERT separately:
--
-- insert into business_agent_private.oauth_clients (client_id, audience)
-- values (
--   '<EXACT_CHATGPT_OAUTH_CLIENT_ID>',
--   'https://research-atlas-api-test.onrender.com/research-advisor/mcp'
-- )
-- on conflict (client_id) do update
-- set audience = excluded.audience, enabled = true;
