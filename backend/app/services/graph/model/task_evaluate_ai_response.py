from pydantic import BaseModel, Field


class TaskEvaluateResult(BaseModel):
    """任务判断结构化结果"""
    task_type: str = Field(description="任务类型，如 chat、new_build、modify")
    enhanced_prompt: str = Field(description="增强后的提示，用于生成代码")

    @classmethod
    def get_response_format(cls) -> dict:
        """JSON 响应格式"""
        return {
            "type": "json_schema",
            "json_schema": {
                "name": cls.__name__,
                "schema": cls.model_json_schema(),
                "strict": True
            }
        }
