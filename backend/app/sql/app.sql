-- 应用表 (PostgreSQL版本)
CREATE TABLE IF NOT EXISTS "app" (
    id               BIGSERIAL PRIMARY KEY,
    app_name         VARCHAR(256) NOT NULL,
    app_coverage     VARCHAR(1024),
    init_prompt      TEXT,
    code_gen_type    VARCHAR(64),
    deploy_key       VARCHAR(64) UNIQUE,
    deploy_time      TIMESTAMP,
    priority         INTEGER DEFAULT 0 NOT NULL,
    user_id          BIGINT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    edit_time        TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    create_time      TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    update_time      TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    is_delete        SMALLINT DEFAULT 0 NOT NULL
);

-- 添加字段注释
COMMENT ON TABLE "app" IS '应用（AI生成的网页应用）';
COMMENT ON COLUMN "app".id IS 'id';
COMMENT ON COLUMN "app".app_name IS '应用名称';
COMMENT ON COLUMN "app".app_coverage IS '应用封面图标URL';
COMMENT ON COLUMN "app".init_prompt IS '应用初始化的用户Prompt';
COMMENT ON COLUMN "app".code_gen_type IS '代码生成类型：枚举值（如html/css/js/multi_file等）';
COMMENT ON COLUMN "app".deploy_key IS '应用部署唯一标识ID';
COMMENT ON COLUMN "app".deploy_time IS '部署时间：未部署时为NULL';
COMMENT ON COLUMN "app".priority IS '首页展示优先级';
COMMENT ON COLUMN "app".user_id IS '创建用户ID（关联user表id）';
COMMENT ON COLUMN "app".edit_time IS '编辑时间：业务代码手动更新（创建者修改时更新）';
COMMENT ON COLUMN "app".create_time IS '创建时间';
COMMENT ON COLUMN "app".update_time IS '更新时间：数据库自动更新（任何修改触发）';
COMMENT ON COLUMN "app".is_delete IS '是否删除：0-正常，1-已删除';

-- 创建普通索引（deploy_key已通过UNIQUE约束自动生成唯一索引）
CREATE INDEX idx_app_name ON "app" (app_name);
CREATE INDEX idx_app_user_id ON "app" (user_id);

-- 复用user表的触发器函数，创建app表的自动更新时间触发器
CREATE TRIGGER update_app_modtime
    BEFORE UPDATE ON "app"
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();