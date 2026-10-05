from backend.app.schemas.responses.ai_generate_results import BaseCodeResult, VueProjectFileCodeResult


def merge_generated_code(old_code: str | BaseCodeResult, new_code: str | BaseCodeResult) -> str | BaseCodeResult:
    """ 合并旧代码和新代码（一般来说是 BaseCodeResult 类型，少数情况下 LLM 返回结果无法解析才是 str 类型） """
    if isinstance(new_code, str) or isinstance(old_code, str):
        return new_code
    if not isinstance(new_code, VueProjectFileCodeResult):
        return new_code
    if not isinstance(old_code, VueProjectFileCodeResult):
        return new_code
    # 对于 VueProjectFileCodeResult 需要合并 code 中新增/修改/删除的文件
    # 确保最终的 vue_project_code_file_paths 中只包含存在的文件，且包含所有文件
    # 新增的文件：加入list
    # 修改的文件：不处理
    # 删除的文件：从list中移除
    for added_file in new_code.added_files:
        old_code.vue_project_code_file_paths.append(added_file)
    for deleted_file in new_code.deleted_files:
        if deleted_file in old_code.vue_project_code_file_paths:
            old_code.vue_project_code_file_paths.remove(deleted_file)
    return old_code
