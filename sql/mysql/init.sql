insert into sys_menu (title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values ('AI', 'PluginAI', '/plugins/ai', 11, 'tabler:robot', 0, null, null, 1, 1, 1, '', null, null, now(), null);

set @ai_menu_id = LAST_INSERT_ID();

insert into sys_menu (title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values ('AI Chat', 'AIChat', '/plugins/ai/chat', 1, 'ri:chat-ai-line', 1, '/plugins/ai/views/chat/index', null, 1, 1, 1, '', null, @ai_menu_id, now(), null);

insert into sys_menu (title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values ('默认模型', 'AIDefaultModel', '/plugins/ai/default-model', 2, 'carbon:model-alt', 1, '/plugins/ai/views/default-model/index', null, 1, 1, 1, '', null, @ai_menu_id, now(), null);

set @ai_default_model_menu_id = LAST_INSERT_ID();

insert into sys_menu (title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values ('模型服务', 'AIModelService', '/plugins/ai/model-service', 3, 'carbon:model-alt', 1, '/plugins/ai/views/model-service/index', null, 1, 1, 1, '', null, @ai_menu_id, now(), null);

set @ai_model_service_menu_id = LAST_INSERT_ID();

insert into sys_menu (title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values ('快捷短语', 'AIQuickPhraseManage', '/plugins/ai/quick-phrase', 4, 'mdi:lightning-bolt-outline', 1, '/plugins/ai/views/quick-phrase/index', null, 1, 1, 1, '', null, @ai_menu_id, now(), null);

set @ai_quick_phrase_menu_id = LAST_INSERT_ID();

insert into sys_menu (title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
('设置默认模型', 'EditAIDefaultModel', null, 0, null, 2, null, 'ai:default-model:edit', 1, 0, 1, '', null, @ai_default_model_menu_id, now(), null),
('新增供应商', 'AddAIProvider', null, 0, null, 2, null, 'ai:provider:add', 1, 0, 1, '', null, @ai_model_service_menu_id, now(), null),
('修改供应商', 'EditAIProvider', null, 0, null, 2, null, 'ai:provider:edit', 1, 0, 1, '', null, @ai_model_service_menu_id, now(), null),
('删除供应商', 'DeleteAIProvider', null, 0, null, 2, null, 'ai:provider:del', 1, 0, 1, '', null, @ai_model_service_menu_id, now(), null),
('新增模型', 'AddAIModel', null, 0, null, 2, null, 'ai:model:add', 1, 0, 1, '', null, @ai_model_service_menu_id, now(), null),
('修改模型', 'EditAIModel', null, 0, null, 2, null, 'ai:model:edit', 1, 0, 1, '', null, @ai_model_service_menu_id, now(), null),
('删除模型', 'DeleteAIModel', null, 0, null, 2, null, 'ai:model:del', 1, 0, 1, '', null, @ai_model_service_menu_id, now(), null),
('新增快捷短语', 'AddAIQuickPhrase', null, 0, null, 2, null, 'ai:quick-phrase:add', 1, 0, 1, '', null, @ai_quick_phrase_menu_id, now(), null),
('修改快捷短语', 'EditAIQuickPhrase', null, 0, null, 2, null, 'ai:quick-phrase:edit', 1, 0, 1, '', null, @ai_quick_phrase_menu_id, now(), null),
('删除快捷短语', 'DeleteAIQuickPhrase', null, 0, null, 2, null, 'ai:quick-phrase:del', 1, 0, 1, '', null, @ai_quick_phrase_menu_id, now(), null);

INSERT INTO ai_provider (id, name, type, api_key, api_host, status, remark, created_time, updated_time, deleted, deleted_time)
VALUES
(1, 'Hb-AI', 0, 'sk-DRde25MlKMIwhLOK0VoFAAw41oudzaZTv944PE8kr91gMOhc', 'http://59.174.170.138:53101/v1', 1, null, '2026-07-22 10:03:48', '2026-07-22 10:04:52', 0, null);

INSERT INTO ai_model (id, provider_id, model_id, status, remark, created_time, updated_time, deleted, deleted_time)
VALUES
(1, 1, 'deepseek-v4-flash', 1, null, '2026-07-22 10:04:06', '2026-07-22 10:05:21', 0, null);

INSERT INTO ai_default_model (id, scene, provider_id, model_id, status, created_time, updated_time, deleted, deleted_time)
VALUES
(1, 'assistant', 1, 'deepseek-v4-flash', 1, '2026-07-22 10:06:16', null, 0, null);