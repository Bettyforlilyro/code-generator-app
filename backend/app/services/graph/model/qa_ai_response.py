from pydantic import BaseModel, Field


class QAResult(BaseModel):
    """代码审查结构化结果"""
    qa_pass: bool = Field(description="综合考虑下，是否给与代码审查通过")
    qa_feedback: str = Field(description="代码审查报告")

    @classmethod
    def get_response_format(cls) -> dict:
        """
        获取代码审查结果的 JSON 格式
        """
        return {
            "type": "json_schema",
            "json_schema": {
                "name": cls.__name__,
                "schema": cls.model_json_schema(),
                "strict": True
            }
        }
