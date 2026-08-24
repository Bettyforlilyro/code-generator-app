-- 用户表 (PostgreSQL版本)
CREATE TABLE IF NOT EXISTS "user" (
    id           BIGSERIAL PRIMARY KEY,
    user_account VARCHAR(256) NOT NULL,
    user_password VARCHAR(512) NOT NULL,
    user_name VARCHAR(256),
    user_avatar VARCHAR(1024),
    user_profile VARCHAR(512),
    user_role VARCHAR(256) DEFAULT 'user' NOT NULL,
    edit_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    is_delete SMALLINT DEFAULT 0 NOT NULL
);

-- 添加字段注释
COMMENT ON TABLE "user" IS '用户';
COMMENT ON COLUMN "user".id IS 'id';
COMMENT ON COLUMN "user".user_account IS '账号';
COMMENT ON COLUMN "user".user_password IS '密码';
COMMENT ON COLUMN "user".user_name IS '用户昵称';
COMMENT ON COLUMN "user".user_avatar IS '用户头像';
COMMENT ON COLUMN "user".user_profile IS '用户简介';
COMMENT ON COLUMN "user".user_role IS '用户角色：user/admin';
COMMENT ON COLUMN "user".edit_time IS '编辑时间';
COMMENT ON COLUMN "user".create_time IS '创建时间';
COMMENT ON COLUMN "user".update_time IS '更新时间';
COMMENT ON COLUMN "user".is_delete IS '是否删除';

-- 创建唯一索引
CREATE UNIQUE INDEX uk_user_account ON "user" (user_account);

-- 创建普通索引
CREATE INDEX idx_user_name ON "user" (user_name);

-- 创建触发器函数实现自动更新 update_time
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.update_time = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 创建触发器
CREATE TRIGGER update_user_modtime
    BEFORE UPDATE ON "user"
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();
