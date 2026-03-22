do $$
declare
    ai_menu_id bigint;
begin
    insert into sys_menu (title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
    values ('ai.menu', 'PluginAI', '/plugins/ai', 11, 'tabler:robot', 1, '/plugins/ai/views/index', null, 1, 1, 1, '', null, (select id from sys_menu where name = 'System'), now(), null)
    returning id into ai_menu_id;

    insert into sys_menu (title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
    values
    ('新增供应商', 'AddAIProvider', null, 0, null, 2, null, 'ai:provider:add', 1, 0, 1, '', null, ai_menu_id, now(), null),
    ('修改供应商', 'EditAIProvider', null, 0, null, 2, null, 'ai:provider:edit', 1, 0, 1, '', null, ai_menu_id, now(), null),
    ('删除供应商', 'DeleteAIProvider', null, 0, null, 2, null, 'ai:provider:del', 1, 0, 1, '', null, ai_menu_id, now(), null),
    ('新增模型', 'AddAIModel', null, 0, null, 2, null, 'ai:model:add', 1, 0, 1, '', null, ai_menu_id, now(), null),
    ('修改模型', 'EditAIModel', null, 0, null, 2, null, 'ai:model:edit', 1, 0, 1, '', null, ai_menu_id, now(), null),
    ('删除模型', 'DeleteAIModel', null, 0, null, 2, null, 'ai:model:del', 1, 0, 1, '', null, ai_menu_id, now(), null),
    ('新增MCP', 'AddAIMcp', null, 0, null, 2, null, 'ai:mcp:add', 1, 0, 1, '', null, ai_menu_id, now(), null),
    ('修改MCP', 'EditAIMcp', null, 0, null, 2, null, 'ai:mcp:edit', 1, 0, 1, '', null, ai_menu_id, now(), null),
    ('删除MCP', 'DeleteAIMcp', null, 0, null, 2, null, 'ai:mcp:del', 1, 0, 1, '', null, ai_menu_id, now(), null);
end $$;

select setval(pg_get_serial_sequence('sys_menu', 'id'), coalesce(max(id), 0) + 1, true) from sys_menu;
