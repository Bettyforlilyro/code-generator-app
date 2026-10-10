ENHANCED_PROMPT_TEMPLATE = """
【网站需求描述】
{user_prompt}

【可用素材资源，请根据描述将素材放入合适的位置】
{material_info}

"""

ENHANCED_PROMPT_MODIFY_TEMPLATE = """
【用户修改要求】
{user_prompt}

【新增/更新的素材资源】
{material_info}

请严格按照修改要求对项目进行增量修改，只修改用户明确要求变更的部分。
"""
