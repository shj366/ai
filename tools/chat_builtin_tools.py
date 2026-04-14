import json
from datetime import datetime, date

from pydantic_ai import Agent, RunContext
from sqlalchemy import inspect, text

from backend.plugin.ai.dataclasses import ChatAgentDeps


def register_chat_builtin_tools(agent: Agent) -> None:
    """
    注册聊天通用函数工具

    :param agent: 聊天代理
    :return:
    """

    @agent.tool_plain
    def get_current_time() -> str:
        """获取当前时间"""
        from backend.utils.timezone import timezone

        return timezone.to_str(timezone.now())

    @agent.tool
    async def list_my_quick_phrases(ctx: RunContext[ChatAgentDeps]) -> list[dict[str, int | str]]:
        """获取当前用户快捷短语列表"""
        from backend.plugin.ai.service.quick_phrase_service import ai_quick_phrase_service

        phrases = await ai_quick_phrase_service.get_all(db=ctx.deps.db, user_id=ctx.deps.user_id)
        return [{'id': item.id, 'title': item.title, 'content': item.content} for item in phrases]

    @agent.tool
    async def list_provider_models(ctx: RunContext[ChatAgentDeps], provider_id: int) -> list[str]:
        """获取指定供应商可用模型 ID"""
        from backend.plugin.ai.crud.crud_model import ai_model_dao

        models = await ai_model_dao.get_all(ctx.deps.db, provider_id=provider_id)
        return [item.model_id for item in models if item.status]

    @agent.tool
    async def get_database_schema(
        ctx: RunContext[ChatAgentDeps],
        table_names: list[str] | None = None,
    ) -> str:
        """
        获取数据库表结构信息，用于智能数据分析的数据准备阶段。

        使用场景：
        - 当用户想让你"分析数据"、"统计数量"或"查询具体业务细节"时，首先调用此工具了解数据库中有什么表，以及这些表长什么样。
        - 如果不确定有哪些表，先传空参数获取所有表名：get_database_schema()
        - 知道表名后，传入表名列表获取具体的列信息（包含字段名、类型和中文注释）：get_database_schema(table_names=["sys_dept"])。

        Args:
            table_names: 要查询结构的表名列表。如果为 None，则返回数据库中所有可用的表名。

        Returns:
            JSON 格式的表结构信息或表名列表。
        """
        conn = await ctx.deps.db.connection()
        def run_inspect(connection):
            inspector = inspect(connection)
            all_tables = inspector.get_table_names()
            
            if not table_names:
                return json.dumps({"available_tables": all_tables}, ensure_ascii=False)
            
            schema_info = {}
            for t in table_names:
                if t in all_tables:
                    cols = inspector.get_columns(t)
                    schema_info[t] = [{"name": c['name'], "type": str(c['type']), "comment": c.get('comment')} for c in cols]
                else:
                    schema_info[t] = "Table not found."
            return json.dumps(schema_info, ensure_ascii=False)
        
        try:
            result = await conn.run_sync(run_inspect)
            return result
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @agent.tool
    async def execute_sql_query(
        ctx: RunContext[ChatAgentDeps],
        sql: str,
    ) -> str:
        """
        执行原生的只读 SQL 查库语句（Text-to-SQL），并返回查询结果。
        这是智能数据分析的核心工具，在了解了表结构之后，编写最高效的 SQL 获取你需要的数据。

        重要限制和规则：
        1. 必须是 SELECT 语句，禁止任何写操作。
        2. 为了防止一次性拉取过大的数据导致内存崩溃，如果在进行宏观分析（如"按年统计"、"计算总数"、"平均值"等），必须在 SQL 层面使用聚合函数（SUM, COUNT, GROUP BY）。绝对不要执行 SELECT * 试图把几十万行数据拉到内存中再统计。
        3. 如果是为了抽样查看数据长什么样，请务必在 SQL 结尾加上 LIMIT (例如 LIMIT 10)。
        4. 结果最多返回 2000 行。如果遇到截断提示，说明你编写的 SQL 不够精简，应该重写你的聚合逻辑。

        Args:
            sql: 要执行的完整的只读 SQL 语句。

        Returns:
            JSON 格式的查询结果列表。
        """
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith("SELECT"):
            return json.dumps({"error": "Only SELECT queries are allowed for safety reasons."}, ensure_ascii=False)
            
        try:
            # 执行原生SQL
            result = await ctx.deps.db.execute(text(sql))
            rows = result.mappings().all()
            
            # 安全限制：如果结果超过2000行，则截断
            if len(rows) > 2000:
                rows_to_return = rows[:2000]
                warning = "Result set exceeded 2000 rows limit. Results have been truncated. Please use aggregation (SUM, COUNT, GROUP BY) or LIMIT in your SQL query for large datasets."
            else:
                rows_to_return = rows
                warning = None
            
            def default_serializer(obj):
                if isinstance(obj, (datetime, date)):
                    return obj.isoformat()
                return str(obj)

            # 转换为字典列表
            data = [dict(row) for row in rows_to_return]
            
            response = {"data": data}
            if warning:
                response["warning"] = warning
                
            return json.dumps(response, default=default_serializer, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": f"SQL Execution Error: {str(e)}"}, ensure_ascii=False)

    @agent.tool
    async def download_attachments(
        ctx: RunContext[ChatAgentDeps],
        entity_type: str,
        entity_ids: list[int],
    ) -> str:
        """
        下载附件压缩包。这是一个通用工具，支持下载各种类型的附件。

        此工具生成下载命令，前端会自动识别并调用下载接口。

        使用示例：
        - 用户说"下载资质1的附件"、"打包资质1的附件" -> entity_type="company_qualification", entity_ids=[1]
        - 用户说"下载专利5的附件" -> entity_type="intellectual_property_patent", entity_ids=[5]
        - 用户说"下载商标1, 3, 5的附件" -> entity_type="intellectual_property_trademark", entity_ids=[1, 3, 5]
        - 用户说"下载员工证书2的附件" -> entity_type="staff_credential", entity_ids=[2]
        - 用户说"打包所有2025年到期的资质附件" -> 先查询获取ID列表，然后使用此工具

        重要说明：
        - 此工具返回JSON格式的下载命令，前端会自动解析并触发下载
        - 返回格式：{"action": "download_attachments", "entity_type": "company_qualification", "entity_ids": [1, 2, 3]}
        - 前端会识别action字段并自动调用下载API

        Args:
            entity_type: 实体类型（必填），例如："company_qualification", "intellectual_property_patent", "intellectual_property_trademark", "intellectual_property_software", "staff_credential"
            entity_ids: 实体ID列表（必填）

        Returns:
            包含下载命令的JSON格式字符串：
            - action: "download_attachments"
            - entity_type: 实体类型
            - entity_ids: 实体ID列表
            - message: 提示信息
        """
        if not entity_ids:
            return json.dumps({
                'action': 'error',
                'message': 'ID list cannot be empty',
            }, ensure_ascii=False)

        result = {
            'action': 'download_attachments',
            'entity_type': entity_type,
            'entity_ids': entity_ids,
            'message': f'prepared to download {len(entity_ids)} {entity_type} attachment files for you, starting download...',
        }

        return json.dumps(result, ensure_ascii=False)
